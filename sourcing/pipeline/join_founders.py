"""Join the Product Hunt founders and the Luma dinner founders into one CSV.

Unifies the two differently-shaped founder lists into a common schema, tagging
each row with its `source`. Dedupes by normalized name; anyone appearing in
both sources is merged into a single row (source="both").
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import config  # noqa: E402


import csv
import re


def norm(name):
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def twitter_url(val):
    if not val:
        return ""
    val = val.strip()
    if val.startswith("http"):
        return val
    return f"https://x.com/{val.lstrip('@')}"


def website_url(val):
    if not val:
        return ""
    return val if val.startswith("http") else "https://" + val


def load_ph():
    """Product Hunt founders + LinkedIn/email from the web-enrichment file."""
    web = {}
    try:
        for r in csv.DictReader(open(config.data_path("producthunt_founder_web_enriched.csv"))):
            web[r["username"]] = r
    except FileNotFoundError:
        pass
    rows = []
    for r in csv.DictReader(open(config.data_path("actual_founders.csv"))):
        w = web.get(r["username"], {})
        rows.append({
            "name": r["name"],
            "source": "producthunt",
            "confidence": r["confidence"],
            "evidence": r["basis"],
            "role_text": r["headline"],
            "context": f"launched: {r['product']} ({r['products_launched']} total)",
            "twitter": twitter_url(r.get("twitter")),
            "linkedin": w.get("linkedin", ""),
            "website": website_url(r.get("website")),
            "email": w.get("emails", ""),
            "profile_url": r["ph_profile"],
        })
    return rows


def load_dinner():
    rows = []
    for r in csv.DictReader(open(config.data_path("dinner_founders.csv"))):
        rows.append({
            "name": r["guest"],
            "source": "dinner",
            "confidence": "high" if r["verdict"] == "founder" else "low",
            "evidence": r["basis"],
            "role_text": r["bio"],
            "context": f"dinner: {r['events']}",
            "twitter": twitter_url(r.get("twitter")),
            "linkedin": r.get("linkedin", ""),
            "website": website_url(r.get("website")),
            "email": r.get("email", ""),
            "profile_url": r["luma_profile"],
        })
    return rows


def merge(a, b):
    """Combine two rows for the same person; prefer filled fields, keep both sources."""
    out = dict(a)
    out["source"] = "both"
    for k, v in b.items():
        if k in ("source", "name"):
            continue
        if not out.get(k) and v:
            out[k] = v
        elif k in ("evidence", "context") and v and v not in out.get(k, ""):
            out[k] = f"{out[k]} | {v}"
    return out


CONF_RANK = {"high": 0, "medium": 1, "low": 2}

if __name__ == "__main__":
    by_name = {}
    for row in load_ph() + load_dinner():
        key = norm(row["name"])
        by_name[key] = merge(by_name[key], row) if key in by_name else row

    founders = sorted(by_name.values(),
                      key=lambda r: (r["source"] != "both",
                                     CONF_RANK.get(r["confidence"], 3),
                                     r["name"].lower()))

    cols = ["name", "source", "confidence", "evidence", "role_text",
            "context", "twitter", "linkedin", "website", "email", "profile_url"]
    with open(config.data_path("all_founders.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(founders)

    ph = sum(r["source"] == "producthunt" for r in founders)
    dn = sum(r["source"] == "dinner" for r in founders)
    both = sum(r["source"] == "both" for r in founders)
    print(f"{len(founders)} founders -> all_founders.csv "
          f"({ph} product hunt, {dn} dinner, {both} in both)\n")
    for r in founders:
        li = " · linkedin" if r["linkedin"] else ""
        em = f" · {r['email']}" if r["email"] else ""
        print(f"  [{r['source']:11} {r['confidence']:>6}] {r['name'][:24]:24} "
              f"{r['role_text'][:34]:34}{li}{em}")
