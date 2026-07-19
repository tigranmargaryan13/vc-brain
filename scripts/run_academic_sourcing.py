#!/usr/bin/env python3
"""Academic sourcing pipeline — merge all channel outputs into one per-founder
dataset and export the CSV for the Lovable data flow.

Channels (each writes <channel>_founder_signals.json via its own script):
  arxiv            scripts/fetch_arxiv_founders.py          (papers + code links)
  semantic_scholar scripts/fetch_semanticscholar_founders.py (citations, h-index)
  openalex         scripts/fetch_openalex_founders.py        (Scholar-equivalent metrics)
  github           scripts/fetch_github_founders.py          (repo builder signals)

Merge key: normalized author name. Signals from multiple channels union per
founder; an existing criterion is never overwritten (first channel wins), so
each fact keeps its original citation. Scoring is positive-only additive
(cold-start rule: a missing signal adds nothing, never subtracts).

Run:            .venv/bin/python scripts/run_academic_sourcing.py
Run + refetch:  .venv/bin/python scripts/run_academic_sourcing.py --fetch
Writes: academic_founders.csv + academic_founder_signals.json (repo root)
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = [
    ("arxiv", "arxiv_founder_signals.json", "fetch_arxiv_founders.py"),
    ("semantic_scholar", "semanticscholar_founder_signals.json",
     "fetch_semanticscholar_founders.py"),
    ("openalex", "openalex_founder_signals.json", "fetch_openalex_founders.py"),
    ("github", "github_founder_signals.json", "fetch_github_founders.py"),
    # runs AFTER the first merge (assesses merged records); folded in on re-merge
    ("potential_assessment", "potential_founder_signals.json",
     "assess_founder_potential.py"),
]
CSV_OUT = os.path.join(REPO, "academic_founders.csv")
JSON_OUT = os.path.join(REPO, "academic_founder_signals.json")

COLUMNS = ["name", "channels", "founder_score", "founder_potential",
           "pre_founding_status", "applied_research", "market_vertical",
           "cold_start", "domain",
           "paper_title", "paper_url", "published", "code_url", "github_handle",
           "repo_stars", "repo_forks", "repo_contributors", "repo_last_push_days",
           "builder_public_repos", "builder_followers", "founder_intent",
           "publication_cadence_12mo", "seed_paper_citations", "author_h_index",
           "author_works_total", "author_citations_total", "affiliation",
           "industry_affiliation", "coauthors", "open_source_release",
           "evidence_urls"]


def norm(name):
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def sig_value(founder, key):
    s = founder["signals"].get(key) or {}
    return s.get("value")


def merge():
    founders = {}
    for channel, fname, _ in CHANNELS:
        path = os.path.join(REPO, fname)
        try:
            rows = json.load(open(path))
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"  ({channel}: no data — skipped)")
            continue
        for rec in rows:
            name = (rec.get("founder") or {}).get("name")
            key = norm(name)
            if not key:
                continue
            f = founders.setdefault(key, {
                "name": name.strip(), "channels": [], "signals": {},
                "founder_meta": {}, "paper": None, "repo": None})
            if channel not in f["channels"]:
                f["channels"].append(channel)
            for k, v in (rec.get("founder") or {}).items():
                if v and not f["founder_meta"].get(k):
                    f["founder_meta"][k] = v
            if rec.get("paper") and not f["paper"]:
                f["paper"] = rec["paper"]
            if rec.get("repo") and not f["repo"]:
                f["repo"] = rec["repo"]
            for crit, sig in (rec.get("signals") or {}).items():
                if crit not in f["signals"]:  # first channel wins, citation intact
                    f["signals"][crit] = {**sig, "channel": channel}
    return list(founders.values())


def score(f):
    """Positive-only additive; absence = unknown = 0 points. Cap 95, floor 35."""
    s = 35
    if sig_value(f, "technical_output_paper"):
        s += 6
    if sig_value(f, "open_source_release") or (f.get("paper") or {}).get("code_url"):
        s += 8
    s += min(int(sig_value(f, "publication_cadence_12mo") or 0) * 2, 12)
    cites = sig_value(f, "earned_attention_citations")
    if cites is not None:
        s += min(int(math.log10(int(cites) + 1) * 6), 12)
    h = sig_value(f, "author_h_index")
    if h is not None:
        s += min(int(h), 10)
    stars = sig_value(f, "repo_stars")
    if stars:
        s += min(int(math.log10(int(stars) + 1) * 5), 10)
    days = sig_value(f, "repo_recent_activity")
    if days is not None and int(days) <= 45:
        s += 4
    if sig_value(f, "industry_affiliation"):
        s += 4
    if sig_value(f, "builder_handle_verified"):
        s += 3
    if sig_value(f, "open_access_release"):
        s += 2
    return max(35, min(int(round(s)), 95))


def to_row(f):
    pa = f.get("paper") or {}
    repo = f.get("repo") or {}
    meta = f.get("founder_meta") or {}
    cats = pa.get("categories") or ([pa.get("topic")] if pa.get("topic") else []) \
        or (pa.get("fields") or [])
    urls, seen = [], set()
    for sig in f["signals"].values():
        u = sig.get("citation")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    days = sig_value(f, "repo_recent_activity")
    bb = sig_value(f, "builder_breadth") or {}
    return {
        "name": f["name"],
        "channels": "|".join(f["channels"]),
        "founder_score": f["founder_score"],
        "founder_potential": sig_value(f, "founder_potential_score"),
        "pre_founding_status": sig_value(f, "pre_founding_status") or "",
        "applied_research": sig_value(f, "applied_research"),
        "market_vertical": sig_value(f, "market_vertical") or "",
        "builder_public_repos": bb.get("public_repos"),
        "builder_followers": bb.get("followers"),
        "founder_intent": bool(sig_value(f, "founder_intent")),
        "cold_start": True,  # channel definition: pre-founding, no company detected
        "domain": "; ".join(str(c) for c in cats[:3] if c),
        "paper_title": pa.get("title") or "",
        "paper_url": pa.get("url") or "",
        "published": pa.get("published") or "",
        "code_url": pa.get("code_url") or repo.get("url") or "",
        "github_handle": meta.get("github") or "",
        "repo_stars": sig_value(f, "repo_stars"),
        "repo_forks": sig_value(f, "repo_forks"),
        "repo_contributors": sig_value(f, "repo_contributors"),
        "repo_last_push_days": days,
        "publication_cadence_12mo": sig_value(f, "publication_cadence_12mo"),
        "seed_paper_citations": sig_value(f, "earned_attention_citations"),
        "author_h_index": sig_value(f, "author_h_index"),
        "author_works_total": sig_value(f, "author_output_total"),
        "author_citations_total": sig_value(f, "author_citations_total"),
        "affiliation": meta.get("affiliation") or "",
        "industry_affiliation": sig_value(f, "industry_affiliation") or "",
        "coauthors": sig_value(f, "coauthor_network"),
        "open_source_release": bool(sig_value(f, "open_source_release")
                                    or pa.get("code_url")),
        "evidence_urls": " | ".join(urls[:6]),
    }


def build():
    founders = merge()
    for f in founders:
        f["founder_score"] = score(f)
    founders.sort(key=lambda f: -f["founder_score"])
    with open(JSON_OUT, "w") as fh:
        json.dump(founders, fh, indent=1, ensure_ascii=False)
    with open(CSV_OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for f in founders:
            w.writerow(to_row(f))
    return founders


def main():
    fetch = "--fetch" in sys.argv
    assess_script = os.path.join(REPO, "scripts", "assess_founder_potential.py")
    if fetch:
        for channel, _, script in CHANNELS:
            if channel == "potential_assessment":
                continue  # needs the merged output; runs after the first build
            print(f"=== fetching {channel} ===")
            subprocess.run([sys.executable, os.path.join(REPO, "scripts", script)],
                           cwd=REPO)
    founders = build()
    if fetch or not os.path.exists(os.path.join(REPO, "potential_founder_signals.json")):
        print("=== assessing founder potential ===")
        subprocess.run([sys.executable, assess_script], cwd=REPO)
        founders = build()  # fold the assessment signals into the outputs

    multi = sum(1 for f in founders if len(f["channels"]) > 1)
    print(f"\nfounders: {len(founders)} | multi-channel: {multi}")
    print(f"scores: {founders[-1]['founder_score']}–{founders[0]['founder_score']}")
    for f in founders[:5]:
        pot = sig_value(f, "founder_potential_score")
        print(f"  {f['founder_score']} (potential {pot})  {f['name']}  "
              f"[{', '.join(f['channels'])}]")
    print(f"\nwrote {CSV_OUT}\nwrote {JSON_OUT}")


if __name__ == "__main__":
    main()
