"""Find the actual founders among the Luma NYC dinner guests.

Unlike the Product Hunt roster, dinner guests have no launch history — the only
title signal is their self-written Luma bio. So: bio states a founder title ->
founder; bio shows another role -> not a founder; NO bio -> unknown (never
"not a founder", per the cold-start rule). Attending a "founders dinner" is not
itself evidence — investors, operators, and press attend those too.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import config  # noqa: E402


import csv
from collections import defaultdict

from find_founders import STRONG_TITLE, WEAK_BUILDING, EMPLOYEE_HINT


def load_unique_guests(path=None):
    path = path or config.data_path("nyc_dinner_guests.csv")
    """Dedupe people across events by api_id; keep richest bio + all events."""
    people = {}
    events = defaultdict(set)
    for r in csv.DictReader(open(path)):
        key = r.get("api_id") or r["guest"]
        events[key].add(r["event"])
        prior = people.get(key)
        if not prior or len(r.get("bio") or "") > len(prior.get("bio") or ""):
            people[key] = r
    for key, r in people.items():
        r["events"] = sorted(events[key])
    return list(people.values())


def classify(bio):
    text = (bio or "").strip()
    if not text:
        return "unknown", "no bio — cannot classify"
    if STRONG_TITLE.search(text):
        return "founder", f'title: "{STRONG_TITLE.search(text).group(0)}"'
    if WEAK_BUILDING.search(text) and not EMPLOYEE_HINT.search(text):
        return "founder-maybe", f'building language: "{WEAK_BUILDING.search(text).group(0)}"'
    return "other-role", "bio present, no founder signal"


if __name__ == "__main__":
    guests = load_unique_guests()
    for g in guests:
        g["verdict"], g["basis"] = classify(g.get("bio"))

    founders = [g for g in guests if g["verdict"] in ("founder", "founder-maybe")]
    founders.sort(key=lambda g: (g["verdict"] != "founder", g["guest"]))

    cols = ["guest", "verdict", "basis", "bio", "events", "linkedin",
            "twitter", "email", "luma_profile"]
    with open(config.data_path("dinner_founders.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for g in founders:
            row = {**g, "events": "; ".join(g["events"])}
            w.writerow(row)

    buckets = defaultdict(int)
    for g in guests:
        buckets[g["verdict"]] += 1
    print(f"{len(guests)} unique dinner guests:")
    for v in ("founder", "founder-maybe", "other-role", "unknown"):
        print(f"  {buckets[v]:>3}  {v}")
    print(f"\n-> dinner_founders.csv ({len(founders)} founders)\n")

    for g in founders:
        li = " · linkedin" if g.get("linkedin") else ""
        tag = "" if g["verdict"] == "founder" else " (maybe)"
        print(f"  {g['guest'][:24]:24}{tag:8} {g['basis']}")
        print(f"        bio: {(g.get('bio') or '')[:66]}{li}")
