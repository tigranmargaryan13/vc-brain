"""Map Product Hunt public data onto VC Brain's TIER-1 sourcing criteria.

Product Hunt can honestly inform a specific slice of the criteria menu — the
Founder-axis "did they build and ship, and did it earn organic attention"
signals — plus weak Idea/Market context (topics, engagement). It cannot see
education, employment history, geography, or intent-departure signals; those
must come from other sources. Absent signals are recorded as None ("unknown"),
never as a negative, per the cold-start rule.

Every signal carries: the criterion name, its axis, tier, positive_only flag,
value, and a citation (the public PH URL backing it) for traceability.

Run:  PRODUCTHUNT_CLIENT_ID=... PRODUCTHUNT_CLIENT_SECRET=... \
      python producthunt_features.py
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import config  # noqa: E402


import csv
import datetime
import json

from retrievers import producthunt as ph

TODAY = datetime.datetime(2026, 7, 19, tzinfo=datetime.timezone.utc)

# Signal metadata mirrors the criteria menu (T1, axis, positive-only).
# Only signals Product Hunt can actually evidence are listed here.
SIGNAL_SPEC = {
    "prior_building_history": ("Founder", "T1", True,
        "Past products actually shipped (count of PH launches)"),
    "serial_founder":         ("Founder", "T1", True,
        "Founded/launched before — >=2 lifetime launches"),
    "shipping_cadence_12mo":  ("Founder", "T1", False,
        "Launches in the last 12 months"),
    "earned_attention_current": ("Founder", "T1", False,
        "Organic upvotes on this launch (not bought)"),
    "earned_attention_career":  ("Founder", "T1", False,
        "Total organic upvotes across all their launches"),
    "earned_attention_peak":    ("Founder", "T1", False,
        "Best single launch by upvotes — ceiling evidence"),
    "building_tenure_days":   ("Founder", "T1", True,
        "Days since first public launch — persistence"),
    "co_founder_present":     ("Founder", "T1", True,
        "Paired vs solo (>=2 makers on the launch)"),
    "domain_focus":           ("Idea-vs-Market", "T1", False,
        "Topic/sector the product plays in (domain tailwind / thesis fit)"),
    "market_engagement":      ("Idea-vs-Market", "T1", False,
        "Comments + reviews — early demand/interest signal"),
    # LLM-judged criteria: we extract the raw text, we do NOT fabricate a score.
    "communication_text":     ("Founder", "T1", False,
        "Raw tagline/description/headline for downstream LLM clarity judging"),
}


def _founder_histories(post_id, first=50, token=None):
    """Return {username: [launch rows]} for every maker + the hunter of a post.

    Each launch row: {name, votes, comments, featuredAt, topics}. This is the
    only way to read a person's launch history at the client-credentials tier
    (the top-level user query is redacted), so we read it nested in a post.
    """
    query = """
    query($id: ID, $first: Int) {
      post(id: $id) {
        makers { username ...H }
        user   { username ...H }
      }
    }
    fragment H on User {
      madePosts(first: $first) {
        edges { node {
          name votesCount commentsCount featuredAt
          topics(first: 5) { edges { node { name } } }
        } }
      }
    }"""
    data = ph.graphql(query, {"id": post_id, "first": first}, token)["post"]
    out = {}
    for person in data["makers"] + [data["user"]]:
        rows = []
        for edge in person["madePosts"]["edges"]:
            n = edge["node"]
            rows.append({
                "name": n["name"],
                "votes": n["votesCount"],
                "comments": n["commentsCount"],
                "featuredAt": n.get("featuredAt"),
                "topics": [e["node"]["name"] for e in n["topics"]["edges"]],
            })
        out[person["username"]] = rows
    return out


def _months_ago(iso):
    if not iso:
        return None
    dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (TODAY - dt).days


def _signal(name, value, citation, evidence=None):
    axis, tier, positive_only, desc = SIGNAL_SPEC[name]
    return {"criterion": name, "axis": axis, "tier": tier,
            "positive_only": positive_only, "description": desc,
            "value": value, "citation": citation, "evidence": evidence}


def founder_features(person, post, history):
    """Build the PH-sourced TIER-1 signal record for one founder on one launch."""
    profile = (person.get("url") or "").split("?")[0]
    product_url = (post.get("url") or "").split("?")[0]

    dates = [_months_ago(h["featuredAt"]) for h in history if h["featuredAt"]]
    launches_12mo = sum(1 for d in dates if d is not None and d <= 365)
    career_votes = sum(h["votes"] for h in history)
    peak_votes = max((h["votes"] for h in history), default=0)
    tenure = max(dates) if dates else None
    total_launched = ph.products_launched(person) or len(history)
    team_size = len(post.get("makers", []))
    topics = [e["node"]["name"] for e in post["topics"]["edges"]]

    signals = {
        "prior_building_history": _signal(
            "prior_building_history", total_launched, profile,
            [h["name"] for h in history]),
        "serial_founder": _signal(
            "serial_founder", total_launched >= 2, profile),
        "shipping_cadence_12mo": _signal(
            "shipping_cadence_12mo", launches_12mo, profile,
            [{"product": h["name"], "featuredAt": h["featuredAt"]}
             for h in history if h["featuredAt"]]),
        "earned_attention_current": _signal(
            "earned_attention_current", post["votesCount"], product_url),
        "earned_attention_career": _signal(
            "earned_attention_career", career_votes, profile),
        "earned_attention_peak": _signal(
            "earned_attention_peak", peak_votes, profile),
        "building_tenure_days": _signal(
            "building_tenure_days", tenure, profile),
        "co_founder_present": _signal(
            "co_founder_present", team_size >= 2, product_url,
            [m["name"] for m in post.get("makers", [])]),
        "domain_focus": _signal(
            "domain_focus", topics, product_url),
        "market_engagement": _signal(
            "market_engagement",
            {"comments": post["commentsCount"], "reviews": post["reviewsCount"],
             "rating": post["reviewsRating"]}, product_url),
        "communication_text": _signal(
            "communication_text",
            {"tagline": post["tagline"], "description": post.get("description"),
             "headline": person.get("headline")}, product_url),
    }

    return {
        "founder": {
            "name": person["name"],
            "username": person["username"],
            "ph_profile": profile,
            "headline": person.get("headline"),
            "twitter": person.get("twitterUsername"),
            "website": person.get("websiteUrl"),
            "is_maker": person.get("isMaker"),
        },
        "launch": {"product": post["name"], "url": product_url,
                   "featured_at": (post.get("featuredAt") or "")[:10]},
        "signals": signals,
    }


def collect(order="RANKING", featured=True, limit=20, history_depth=50, token=None):
    """Collect PH founder feature records for a batch of launches."""
    posts = ph.get_posts(order=order, featured=featured, limit=limit, token=token)
    records = []
    for post in posts:
        histories = _founder_histories(post["id"], first=history_depth, token=token)
        for person in post["makers"]:
            hist = histories.get(person["username"], [])
            records.append(founder_features(person, post, hist))
    return records


def to_flat_rows(records):
    """Flatten to one CSV-friendly row per founder (values only, no metadata)."""
    rows = []
    for r in records:
        s = r["signals"]
        f = r["founder"]
        rows.append({
            "founder": f["name"], "username": f["username"],
            "product": r["launch"]["product"],
            "current_votes": s["earned_attention_current"]["value"],
            "career_votes": s["earned_attention_career"]["value"],
            "peak_votes": s["earned_attention_peak"]["value"],
            "products_launched": s["prior_building_history"]["value"],
            "serial_founder": s["serial_founder"]["value"],
            "launches_12mo": s["shipping_cadence_12mo"]["value"],
            "tenure_days": s["building_tenure_days"]["value"],
            "co_founder_present": s["co_founder_present"]["value"],
            "team_size": len(s["co_founder_present"]["evidence"] or []),
            "topics": "; ".join(s["domain_focus"]["value"]),
            "comments": s["market_engagement"]["value"]["comments"],
            "twitter": f["twitter"], "website": f["website"],
            "headline": f["headline"], "ph_profile": f["ph_profile"],
        })
    return rows


if __name__ == "__main__":
    try:
        ph._resolve_token()
    except RuntimeError as err:
        raise SystemExit(f"\n{err}\n")

    records = collect(limit=20)

    with open(config.data_path("producthunt_founder_signals.json"), "w") as f:
        json.dump(records, f, indent=2)
    rows = to_flat_rows(records)
    cols = list(rows[0].keys())
    with open(config.data_path("producthunt_founder_signals.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(records)} founder records from 20 launches")
    print("  -> producthunt_founder_signals.json (full signals + citations)")
    print("  -> producthunt_founder_signals.csv  (flat values)\n")

    print("Top founders by career earned-attention (organic PH upvotes):")
    for r in sorted(rows, key=lambda x: -x["career_votes"])[:10]:
        flags = []
        if r["serial_founder"]:
            flags.append("serial")
        if r["launches_12mo"] >= 3:
            flags.append(f"{r['launches_12mo']}x/12mo")
        if not r["co_founder_present"]:
            flags.append("solo")
        tag = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  {r['career_votes']:>6} career votes | {r['products_launched']:>2} launched | "
              f"@{r['username']:16} {r['founder'][:22]:22}{tag}")
