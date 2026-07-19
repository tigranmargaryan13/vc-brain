"""Enrich the joined founder list with product/company, industry, location, and
a verified GitHub username/repo link.

Sources per field (free/public only; absent -> "unknown", never guessed):
  * product/company : PH launch (product) | extracted from the dinner bio
  * industry        : PH topics (sector tags) | light keyword inference for dinner
  * location        : verified GitHub location | NYC inferred from Luma timezone
  * github          : verified only (type=User + name match) so we don't attach
                      the wrong person's repos
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import config  # noqa: E402


import csv
import os
import re
import time

import requests

GH_HEADERS = {"Accept": "application/vnd.github+json",
              "X-GitHub-Api-Version": "2022-11-28"}
if os.environ.get("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
_session = requests.Session()

# "co-founder @ MindFort", "Co-Founder of Alinea", "CEO, Aira Security".
# Company tokens exclude '.' so we stop at a sentence break ("CouWed. My work").
COMPANY_RE = re.compile(
    r"(?:co[-\s]?founder|founder|ceo|cto|founding)\b[^@,\n]*?"
    r"(?:@|\bof\b|\bat\b|,)\s+([A-Z][\w&'’-]*(?:\s+[A-Z0-9][\w&'’-]*){0,3})")


def tz_location(tz):
    """Readable location from a Luma timezone (their profile region)."""
    if not tz:
        return ""
    return tz.split("/")[-1].replace("_", " ") + " (tz)"

INDUSTRY_KW = [
    ("ai", "AI/ML"), ("ml", "AI/ML"), ("robot", "Robotics"), ("security", "Security"),
    ("fintech", "Fintech"), ("finance", "Fintech"), ("health", "Health"),
    ("med", "Health"), ("design", "Design"), ("education", "Education"),
    ("tutor", "Education"), ("marketing", "Marketing"), ("commerce", "E-Commerce"),
    ("data", "Data"), ("dev", "Developer Tools"), ("sales", "Sales"),
]


def _gh(path, state):
    if state["rate_limited"]:
        return None
    r = _session.get(f"https://api.github.com{path}", headers=GH_HEADERS, timeout=20)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        state["rate_limited"] = True
        return None
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _tokens(name):
    return {t for t in re.split(r"\W+", (name or "").lower()) if len(t) >= 3}


def resolve_github(name, candidates, state):
    """Return {username, url, location, company} for a verified personal match."""
    want = _tokens(name)
    seen = set()
    for cand in candidates:
        cand = (cand or "").strip().lstrip("@")
        if not cand or cand.lower() in seen or "/" in cand:
            continue
        seen.add(cand.lower())
        prof = _gh(f"/users/{cand}", state)
        if not prof or prof.get("type") != "User":
            continue
        if want & _tokens(prof.get("name")):
            return {"username": prof["login"], "url": prof["html_url"],
                    "location": prof.get("location"), "company": prof.get("company")}
    return None


def infer_industry(text):
    t = (text or "").lower()
    hits = []
    for kw, label in INDUSTRY_KW:
        if kw in t and label not in hits:
            hits.append(label)
    return "; ".join(hits[:3])


def extract_company(bio):
    m = COMPANY_RE.search(bio or "")
    return m.group(1).strip() if m else ""


def load_sources():
    ph_topics, web = {}, {}
    for r in csv.DictReader(open(config.data_path("producthunt_launch_teams.csv"))):
        ph_topics.setdefault(r["username"], r["topics"])
    for r in csv.DictReader(open(config.data_path("producthunt_founder_web_enriched.csv"))):
        web[r["username"]] = r
    dinner_tz = {}
    for r in csv.DictReader(open(config.data_path("nyc_dinner_guests.csv"))):
        dinner_tz[r["guest"]] = r.get("timezone")
    return ph_topics, web, dinner_tz


def load_overview():
    """Product overview + characteristics from the earlier collected files."""
    import json
    launch = {}
    for r in csv.DictReader(open(config.data_path("producthunt_launch_teams.csv"))):
        launch.setdefault(r["username"], r)
    desc = {}
    try:
        for rec in json.load(open(config.data_path("producthunt_founder_signals.json"))):
            desc[rec["founder"]["username"]] = \
                rec["signals"]["communication_text"]["value"].get("description")
    except FileNotFoundError:
        pass
    enr = {}
    try:
        for rec in json.load(open(config.data_path("founder_enriched.json"))):
            fd = rec["signals"]["fresh_domain"]["value"]
            ea = rec["signals"]["earned_attention"]["value"]
            enr[rec["founder"]["username"]] = {
                "age": fd.get("domain_age_days"), "fresh": fd.get("is_fresh"),
                "hn": ea.get("hn_peak_points")}
    except FileNotFoundError:
        pass
    dinner_bio = {r["guest"]: r["bio"] for r in csv.DictReader(open(config.data_path("dinner_founders.csv")))}
    return launch, desc, enr, dinner_bio


def add_overview(row):
    """Attach product overview + metrics to a founder row (in place)."""
    launch, desc, enr, dinner_bio = load_overview.cache
    blank = dict(product_overview="", description="", upvotes="", comments="",
                 launched="", domain_age_days="", fresh_domain="", hn_points="",
                 product_url="")
    row.update(blank)
    if row["source"] == "producthunt":
        u = row["profile_url"].split("@")[-1] if "@" in row["profile_url"] else ""
        L, e = launch.get(u, {}), enr.get(u, {})
        row["product_overview"] = L.get("tagline", "")
        row["description"] = desc.get(u) or ""
        row["upvotes"] = L.get("votes", "")
        row["comments"] = L.get("comments", "")
        row["launched"] = L.get("featured_at", "")
        row["product_url"] = L.get("product_url", "")
        if e.get("age") is not None:
            row["domain_age_days"] = e["age"]
            row["fresh_domain"] = "Y" if e.get("fresh") else "N"
        row["hn_points"] = e.get("hn") or ""
    else:
        row["product_overview"] = dinner_bio.get(row["name"], "")
    return row


def build():
    ph_topics, web, dinner_tz = load_sources()
    ph = {r["username"]: r for r in csv.DictReader(open(config.data_path("actual_founders.csv")))}
    dinner = list(csv.DictReader(open(config.data_path("dinner_founders.csv"))))
    state = {"rate_limited": False}
    rows = []

    # ---- Product Hunt founders
    for u, r in ph.items():
        w = web.get(u, {})
        gh_cand = []
        if w.get("github") and "/orgs" not in w["github"]:
            gh_cand.append(w["github"].rstrip("/").split("/")[-1])
        gh_cand += [u, (r.get("twitter") or "").lstrip("@")]
        gh = resolve_github(r["name"], gh_cand, state) or {}
        rows.append({
            "name": r["name"], "source": "producthunt",
            "product_company": r["product"].strip(),
            "industry": ph_topics.get(u, ""),
            "location": gh.get("location") or "",
            "github_username": gh.get("username") or "",
            "github_url": gh.get("url") or "",
            "website": r.get("website") or w.get("resolved_url") or "",
            "linkedin": w.get("linkedin") or "",
            "profile_url": r["ph_profile"],
        })
        time.sleep(0.2)

    # ---- Dinner founders
    for r in dinner:
        name = r["guest"]
        company = extract_company(r["bio"])
        tz = dinner_tz.get(name) or ""
        gh = resolve_github(name, [(r.get("twitter") or "").lstrip("@")], state) or {}
        location = gh.get("location") or tz_location(tz)
        rows.append({
            "name": name, "source": "dinner",
            "product_company": company,
            "industry": infer_industry(f"{company} {r['bio']}"),
            "location": gh.get("location") or location,
            "github_username": gh.get("username") or "",
            "github_url": gh.get("url") or "",
            "website": r.get("website") or "",
            "linkedin": r.get("linkedin") or "",
            "profile_url": r["luma_profile"],
        })
        time.sleep(0.2)

    load_overview.cache = load_overview()
    for row in rows:
        add_overview(row)
    return rows, state


if __name__ == "__main__":
    rows, state = build()
    cols = ["name", "source", "product_company", "product_overview", "description",
            "industry", "upvotes", "comments", "launched", "domain_age_days",
            "fresh_domain", "hn_points", "location", "github_username", "github_url",
            "website", "product_url", "linkedin", "profile_url"]
    with open(config.data_path("founder_product_info.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    have = lambda k: sum(1 for r in rows if r[k])
    rl = " (GitHub rate-limited partway)" if state["rate_limited"] else ""
    print(f"{len(rows)} founders -> founder_product_info.csv{rl}")
    print(f"  product/company: {have('product_company')}  industry: {have('industry')}  "
          f"location: {have('location')}  github: {have('github_username')}\n")
    for r in rows:
        gh = f" gh:{r['github_username']}" if r["github_username"] else ""
        print(f"  [{r['source'][:2]}] {r['name'][:22]:22} | {(r['product_company'] or '?')[:18]:18}"
              f" | {(r['industry'] or '?')[:22]:22} | {(r['location'] or '?')[:20]:20}{gh}")
