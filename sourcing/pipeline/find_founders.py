"""Filter the Product Hunt roster down to people who are *actually* founders.

Not everyone on a launch is a founder: hunters often just post links, and
makers can be employees, designers, or freelancers. We classify each person
from the evidence we already collected — their self-described headline/bio,
GitHub company, and launch track record — and keep only those the evidence
supports as founders.

Honesty note: a headline saying "Founder" is a self-claim (Tier-1, unverified);
real verification is the Tier-2 step. We tag the basis so it's auditable.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import config  # noqa: E402


import csv
import json
import re

# Strong: an explicit founder/chief-executive title only. Deliberately excludes
# "founding engineer/member" and "CTO/Head of" — those are early-operator or
# leadership roles, not proof of being a founder (a separate criterion).
# Singular titles only: plural "founders" is almost always the object of
# "helping/advising founders" (an investor/advisor), not the person's own title.
STRONG_TITLE = re.compile(
    r"\b(co[-\s]?founder|founder|ceo|chief\s+executive|solo[-\s]?founder)\b(?!s)", re.I)
WEAK_BUILDING = re.compile(
    r"\b(building\s+(?:my|our|a|the)\b|creator\s+of|maker\s+of|i\s+built|"
    r"bootstrapp|indie\s+hacker|running\s+my)\b", re.I)
# Employee/early-operator tells that should NOT count as founder on their own.
EMPLOYEE_HINT = re.compile(
    r"\b((?:engineer|developer|designer|pm|intern|head\s+of\s+\w+)\s+at\b|"
    r"founding\s+(?:engineer|member))", re.I)


def load_people():
    """One row per unique person, merging launch roster + web bios + GitHub company."""
    web = {}
    try:
        for r in csv.DictReader(open(config.data_path("producthunt_founder_web_enriched.csv"))):
            web[r["username"]] = r
    except FileNotFoundError:
        pass

    gh_company = {}
    try:
        for r in json.load(open(config.data_path("founder_enriched.json"))):
            comp = r["signals"]["pedigree_company"]["value"]
            if comp:
                gh_company[r["founder"]["username"]] = comp
    except FileNotFoundError:
        pass

    people = {}
    for r in csv.DictReader(open(config.data_path("producthunt_launch_teams.csv"))):
        u = r["username"]
        prior = people.get(u)
        # prefer the 'maker' row over a 'hunter' row for the same person
        if prior and prior["role"] == "maker":
            continue
        w = web.get(u, {})
        people[u] = {
            "name": r["person"], "username": u, "role": r["role"],
            "product": r["product"], "headline": r.get("headline") or "",
            "bio": w.get("bio") or "",
            "github_company": gh_company.get(u) or "",
            "products_launched": int(r["products_launched"] or 0),
            "twitter": r.get("twitter") or "", "website": r.get("website_personal") or "",
            "ph_profile": r["ph_profile"],
        }
    return list(people.values())


def classify(p):
    """Return (is_founder, basis, confidence) from the available evidence."""
    text = " | ".join([p["headline"], p["bio"], p["github_company"]]).strip(" |")

    if STRONG_TITLE.search(text):
        return True, f"stated title: \"{_hit(STRONG_TITLE, text)}\"", "high"
    # Serial launcher with building language, but no explicit title
    if p["products_launched"] >= 3 and WEAK_BUILDING.search(text):
        return True, f"serial builder ({p['products_launched']} launches) + building language", "medium"
    if p["products_launched"] >= 3 and not EMPLOYEE_HINT.search(text):
        return True, f"serial builder ({p['products_launched']} launches)", "medium"
    if WEAK_BUILDING.search(text) and not EMPLOYEE_HINT.search(text):
        return True, f"building language: \"{_hit(WEAK_BUILDING, text)}\"", "low"
    return False, "no founder evidence", "-"


def _hit(pattern, text):
    m = pattern.search(text)
    return m.group(0) if m else ""


CONF_RANK = {"high": 0, "medium": 1, "low": 2, "-": 3}

if __name__ == "__main__":
    people = load_people()
    for p in people:
        p["is_founder"], p["basis"], p["confidence"] = classify(p)

    founders = [p for p in people if p["is_founder"]]
    founders.sort(key=lambda p: (CONF_RANK[p["confidence"]], -p["products_launched"]))

    cols = ["name", "username", "confidence", "basis", "products_launched",
            "product", "headline", "twitter", "website", "ph_profile"]
    with open(config.data_path("actual_founders.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(founders)

    n_high = sum(p["confidence"] == "high" for p in founders)
    print(f"{len(founders)} of {len(people)} people classified as founders "
          f"({n_high} high-confidence) -> actual_founders.csv\n")
    for p in founders:
        print(f"  [{p['confidence']:>6}] {p['name'][:22]:22} @{p['username']:16} "
              f"{p['products_launched']:>2} launches | {p['basis']}")

    dropped = [p for p in people if not p["is_founder"]]
    print(f"\nNot classified as founders ({len(dropped)}) — hunters/unclear headlines, e.g.:")
    for p in dropped[:8]:
        print(f"    {p['name'][:22]:22} @{p['username']:16} role={p['role']:6} "
              f"headline={p['headline'][:30]!r}")
