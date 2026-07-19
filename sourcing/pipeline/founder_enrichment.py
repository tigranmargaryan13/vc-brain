"""Unified cross-source founder enrichment against the VC Brain criteria menu.

Fuses the free public sources we can reach — Product Hunt (already collected),
GitHub, Hacker News, and domain-registration (RDAP) — into one founder record,
each signal tagged with axis / tier / positive_only / source / citation.

Design rules straight from the criteria menu:
  * Absence of a signal is recorded as None ("unknown"), never a negative.
  * Bias-flagged signals (geography, pedigree) are captured but marked weak.
  * LLM-judged criteria (communication clarity, ambition, originality) are left
    as an extracted text corpus — we collect, we do not fabricate a score.
  * Criteria that need gated/paid data (education, layoffs, network graph) are
    listed in the coverage map as NOT free-collectable, honestly.

Run:  GITHUB_TOKEN=... python founder_enrichment.py     (token optional but
      lifts GitHub's 60/hr unauth limit to 5000/hr)
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import config  # noqa: E402


import csv
import datetime
import json
import os
import re
import time

import requests

from retrievers import hackernews as hn

TODAY = datetime.datetime(2026, 7, 19, tzinfo=datetime.timezone.utc)
GH_HEADERS = {"Accept": "application/vnd.github+json",
              "X-GitHub-Api-Version": "2022-11-28"}
if os.environ.get("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

_session = requests.Session()


# --------------------------------------------------------------- data loading
def load_founders():
    """Merge the Product Hunt roster + web-enrichment into base founder rows."""
    web = {}
    try:
        for r in csv.DictReader(open(config.data_path("producthunt_founder_web_enriched.csv"))):
            web[r["username"]] = r
    except FileNotFoundError:
        pass

    founders = {}
    for r in csv.DictReader(open(config.data_path("producthunt_launch_teams.csv"))):
        if r["role"] != "maker":
            continue
        u = r["username"]
        if u in founders:
            continue
        w = web.get(u, {})
        founders[u] = {
            "name": r["person"], "username": u, "ph_profile": r["ph_profile"],
            "product": r["product"], "product_website": r["website"],
            "topics": r["topics"], "current_votes": int(r["votes"] or 0),
            "products_launched": int(r["products_launched"] or 0),
            "team_size_hint": None,
            "personal_website": w.get("resolved_url") or r.get("website_personal"),
            "email": w.get("emails") or None,
            "github_url": w.get("github") or None,
            "linkedin_url": w.get("linkedin") or None,
            "twitter_handle": (r.get("twitter") or "").lstrip("@") or None,
            "bio": w.get("bio") or r.get("headline"),
        }
    return list(founders.values())


# ------------------------------------------------------------------- GitHub
def _gh(path):
    r = _session.get(f"https://api.github.com{path}", headers=GH_HEADERS, timeout=20)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        raise RuntimeError("github_rate_limited")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _name_tokens(name):
    return {t for t in re.split(r"\W+", (name or "").lower()) if len(t) >= 3}


def resolve_github(founder, state):
    """Verify a GitHub handle really belongs to this person (type=User + name
    overlap). Filters orgs and false positives like a linked project repo."""
    if state.get("rate_limited"):
        return None
    candidates = []
    if founder["github_url"]:
        candidates.append(founder["github_url"].rstrip("/").split("/")[-1])
    candidates.append(founder["username"])
    if founder["twitter_handle"]:
        candidates.append(founder["twitter_handle"])

    want = _name_tokens(founder["name"])
    seen = set()
    for cand in candidates:
        cand = cand.strip()
        if not cand or cand.lower() in seen:
            continue
        seen.add(cand.lower())
        try:
            prof = _gh(f"/users/{cand}")
        except RuntimeError:
            state["rate_limited"] = True
            return None
        if not prof or prof.get("type") != "User":
            continue
        # accept if the GitHub display name shares a token with the founder name
        if want & _name_tokens(prof.get("name")):
            return prof
    return None


def github_signals(prof, state):
    """Profile + repo-derived signals, or {} if no verified profile."""
    if not prof:
        return {}
    try:
        repos = _gh(f"/users/{prof['login']}/repos?per_page=100&sort=pushed") or []
    except RuntimeError:
        state["rate_limited"] = True
        repos = []
    originals = [r for r in repos if not r["fork"]]
    langs = sorted({r["language"] for r in originals if r["language"]})
    recent_push = max((r.get("pushed_at") or "" for r in originals), default="")
    return {
        "login": prof["login"],
        "location": prof.get("location"),
        "company": prof.get("company"),
        "followers": prof.get("followers"),
        "public_repos": prof.get("public_repos"),
        "blog": prof.get("blog") or None,
        "twitter": prof.get("twitter_username"),
        "total_stars": sum(r["stargazers_count"] for r in originals),
        "peak_stars": max((r["stargazers_count"] for r in originals), default=0),
        "languages": langs,
        "recent_push": recent_push[:10],
        "pushed_last_6mo": recent_push[:7] >= "2026-01",
        "top_repos": [
            {"name": r["name"], "stars": r["stargazers_count"],
             "desc": r.get("description")}
            for r in sorted(originals, key=lambda x: -x["stargazers_count"])[:3]
        ],
    }


# --------------------------------------------------------------------- RDAP
_domain_cache = {}


def _real_domain(url):
    """Resolve the real product host, following Product Hunt's /r/ redirect.

    PH's `website` field is a producthunt.com/r/<id> tracking redirect, so we
    must follow it to reach the actual product domain before an RDAP lookup.
    """
    if url in _domain_cache:
        return _domain_cache[url]
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].split("?")[0].split(":")[0].lower()
    if host.endswith("producthunt.com"):
        try:
            r = _session.get(url, headers={"User-Agent": "vc-brain-enricher/1.0"},
                             timeout=15, allow_redirects=True)
            host = re.sub(r"^https?://(www\.)?", "", r.url).split("/")[0].lower()
        except requests.RequestException:
            host = None
    result = host if host and "." in host and not host.endswith("producthunt.com") else None
    _domain_cache[url] = result
    return result


def domain_age_days(url):
    """Days since the product domain was registered (fresh-domain intent)."""
    if not url:
        return None
    host = _real_domain(url)
    if not host:
        return None
    try:
        r = _session.get(f"https://rdap.org/domain/{host}", timeout=20,
                         allow_redirects=True)
        if r.status_code != 200:
            return None
        events = {e["eventAction"]: e["eventDate"] for e in r.json().get("events", [])}
        reg = events.get("registration")
        if not reg:
            return None
        dt = datetime.datetime.fromisoformat(reg.replace("Z", "+00:00"))
        return (TODAY - dt).days
    except (requests.RequestException, ValueError, KeyError):
        return None


# ----------------------------------------------------------------------- HN
def hn_attention(product, name):
    """Earned attention on Hacker News for the product/founder."""
    try:
        hits = hn.search(product, tags="story", max_pages=1)
    except Exception:
        return {}
    # keep hits whose title actually contains the product name (reduce noise)
    p = product.lower()
    matched = [h for h in hits if p in (h.get("title") or "").lower()]
    return {
        "product_hits": len(matched),
        "peak_points": max((h["points"] for h in matched), default=0),
        "peak_url": (f"https://news.ycombinator.com/item?id={matched[0]['objectID']}"
                     if matched else None),
    }


# ------------------------------------------------------------- assemble record
# criterion -> (axis, tier, positive_only)
CRITERIA = {
    "technical_output": ("Founder", "T1", False),
    "shipping_cadence": ("Founder", "T1", False),
    "earned_attention": ("Founder", "T1", False),
    "prior_building_history": ("Founder", "T1", True),
    "serial_founder": ("Founder", "T1", True),
    "domain_tailwind": ("Idea-vs-Market", "T1", False),
    "geography": ("Founder", "T1", True),          # bias: weak positive only
    "pedigree_company": ("Founder", "T1", True),   # bias: weak positive only
    "fresh_domain": ("Idea-vs-Market", "T1", True),
    "community_presence": ("Founder", "T1", True),
    "communication_corpus": ("Founder", "T1", False),
}


def sig(name, value, source, citation):
    axis, tier, positive_only = CRITERIA[name]
    return {"value": value, "axis": axis, "tier": tier,
            "positive_only": positive_only, "source": source, "citation": citation}


def enrich(founder, state):
    prof = resolve_github(founder, state)
    gh = github_signals(prof, state)
    age = domain_age_days(founder["product_website"])
    hnx = hn_attention(founder["product"], founder["name"])
    topics = [t.strip() for t in (founder["topics"] or "").split(";") if t.strip()]

    ph_cite = founder["ph_profile"]
    gh_cite = f"https://github.com/{gh['login']}" if gh else None

    signals = {
        "prior_building_history": sig("prior_building_history",
            {"ph_launches": founder["products_launched"],
             "github_repos": gh.get("public_repos")}, "producthunt+github", ph_cite),
        "serial_founder": sig("serial_founder",
            founder["products_launched"] >= 2, "producthunt", ph_cite),
        "shipping_cadence": sig("shipping_cadence",
            {"github_recent_push": gh.get("recent_push"),
             "pushed_last_6mo": gh.get("pushed_last_6mo")}, "github", gh_cite),
        "technical_output": sig("technical_output",
            {"languages": gh.get("languages"), "top_repos": gh.get("top_repos")}
            if gh else None, "github", gh_cite),
        "earned_attention": sig("earned_attention",
            {"ph_votes": founder["current_votes"], "github_stars": gh.get("total_stars"),
             "github_followers": gh.get("followers"),
             "hn_peak_points": hnx.get("peak_points")}, "producthunt+github+hn",
            ph_cite),
        "domain_tailwind": sig("domain_tailwind", topics, "producthunt",
            founder.get("ph_profile")),
        "geography": sig("geography", gh.get("location"), "github", gh_cite),
        "pedigree_company": sig("pedigree_company", gh.get("company"), "github", gh_cite),
        "fresh_domain": sig("fresh_domain",
            {"domain_age_days": age, "is_fresh": (age is not None and age <= 180)},
            "rdap", founder["product_website"]),
        "community_presence": sig("community_presence",
            {"ph_repeat_launcher": founder["products_launched"] >= 3,
             "hn_presence": hnx.get("product_hits", 0) > 0}, "producthunt+hn", ph_cite),
        "communication_corpus": sig("communication_corpus",
            {"bio": founder["bio"], "github_bio": (prof or {}).get("bio"),
             "repo_descriptions": [r["desc"] for r in gh.get("top_repos", [])]},
            "multi", ph_cite),
    }

    return {
        "founder": {k: founder[k] for k in
                    ("name", "username", "ph_profile", "personal_website",
                     "email", "linkedin_url", "twitter_handle")},
        "github_matched": bool(gh),
        "signals": signals,
    }


def coverage_report(records):
    """How many founders got each criterion filled (non-null value)."""
    def filled(s):
        v = s["value"]
        if v is None:
            return False
        if isinstance(v, dict):
            return any(x not in (None, [], "", 0, False) for x in v.values())
        return v not in ([], "", 0, False)
    n = len(records)
    out = {}
    for crit in CRITERIA:
        c = sum(1 for r in records if filled(r["signals"][crit]))
        out[crit] = f"{c}/{n}"
    return out


if __name__ == "__main__":
    founders = load_founders()
    # Bound the batch to respect GitHub's unauth rate limit; rank by PH votes.
    founders = sorted(founders, key=lambda f: -f["current_votes"])[:12]

    state = {"rate_limited": False}
    records = []
    for i, f in enumerate(founders, 1):
        rec = enrich(f, state)
        records.append(rec)
        gh = "gh:Y" if rec["github_matched"] else "gh:-"
        rl = " (gh rate-limited)" if state["rate_limited"] else ""
        print(f"  [{i}/{len(founders)}] {f['username']:16} {gh}{rl}")
        time.sleep(0.3)

    with open(config.data_path("founder_enriched.json"), "w") as fh:
        json.dump(records, fh, indent=2)

    print("\nCOVERAGE (founders with a non-null value per criterion):")
    for crit, frac in coverage_report(records).items():
        axis, tier, po = CRITERIA[crit]
        flag = " [+only]" if po else ""
        print(f"  {frac:>6}  {crit:24} {axis}/{tier}{flag}")

    print("\nNOT free-collectable (recorded as unknown, per cold-start rule):")
    for c in ["education (STEM/advanced/top-tier)", "layoff / dropout / departure",
              "network drift / followed-by-notables", "risk tolerance (left a job)",
              "prior exit / early-operator pedigree (needs Crunchbase/news)"]:
        print(f"  - {c}")
    print("\n  -> founder_enriched.json")
