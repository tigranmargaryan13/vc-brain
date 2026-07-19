#!/usr/bin/env python3
"""GitHub repo-enrichment channel — "builder behavior" signals for the code
repositories referenced in sourced papers (stars, forks, recency, contributors).
Consumes arxiv_founder_signals.json (papers with code links) and enriches each
author's linked repo via the GitHub API. Unauthenticated works (60 req/hr);
GITHUB_TOKEN in .env raises the limit.

Same signals contract as the other channels; a repo that 404s is skipped —
absence is unknown, never negative.

Run: .venv/bin/python scripts/fetch_github_founders.py
Writes: github_founder_signals.json (repo root)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(REPO_DIR, "arxiv_founder_signals.json")
OUT = os.path.join(REPO_DIR, "github_founder_signals.json")

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if os.getenv("GITHUB_TOKEN"):
    HEADERS["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"


def _sig(criterion, description, value, citation, evidence=None, positive_only=False):
    return {"criterion": criterion, "axis": "Founder", "tier": "T1",
            "positive_only": positive_only, "description": description,
            "value": value, "citation": citation, "evidence": evidence}


def contributors_count(owner, repo):
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/contributors",
                     params={"per_page": 1, "anon": "true"}, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return None
    m = re.search(r'page=(\d+)>; rel="last"', r.headers.get("Link", ""))
    return int(m.group(1)) if m else len(r.json())


def main():
    try:
        rows = json.load(open(IN))
    except FileNotFoundError:
        print(f"missing {IN} — run scripts/fetch_arxiv_founders.py first")
        return 1

    records, seen_repos = [], set()
    now = datetime.now(timezone.utc)
    for rec in rows:
        code_url = (rec.get("paper") or {}).get("code_url")
        name = (rec.get("founder") or {}).get("name")
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)", code_url or "")
        if not m or not name:
            continue
        owner, repo = m.group(1), m.group(2)
        key = f"{owner}/{repo}".lower()
        if key in seen_repos:
            continue
        seen_repos.add(key)

        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}",
                         headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  - {name}: {key} -> HTTP {r.status_code}, skipped")
            continue
        d = r.json()
        time.sleep(0.5)
        contribs = contributors_count(owner, repo)
        time.sleep(0.5)

        pushed = d.get("pushed_at")
        days_since_push = None
        if pushed:
            days_since_push = (now - datetime.fromisoformat(
                pushed.replace("Z", "+00:00"))).days

        html = d.get("html_url") or code_url
        signals = {
            "repo_stars": _sig(
                "repo_stars", "GitHub stars on the paper's code repo — earned attention",
                d.get("stargazers_count", 0), html),
            "repo_forks": _sig(
                "repo_forks", "Forks on the paper's code repo — community reuse",
                d.get("forks_count", 0), html),
        }
        if contribs is not None:
            signals["repo_contributors"] = _sig(
                "repo_contributors", "Contributor count — collaboration signal",
                contribs, f"{html}/graphs/contributors")
        if days_since_push is not None:
            signals["repo_recent_activity"] = _sig(
                "repo_recent_activity",
                "Days since last push — active maintenance / shipping cadence",
                days_since_push, html,
                positive_only=True)
        gh_handle = (rec.get("founder") or {}).get("github")
        if gh_handle and gh_handle.lower() == owner.lower():
            signals["builder_handle_verified"] = _sig(
                "builder_handle_verified",
                "Repo owner matches the paper author — direct builder evidence",
                True, f"https://github.com/{owner}", positive_only=True)

        records.append({
            "channel": "github",
            "founder": {"name": name, "github": gh_handle},
            "repo": {"url": html, "owner": owner, "name": d.get("name"),
                     "language": d.get("language"), "pushed_at": pushed,
                     "created_at": d.get("created_at")},
            "signals": signals,
        })
        print(f"  + {name}: {key} — ★{d.get('stargazers_count')} "
              f"forks {d.get('forks_count')} contribs {contribs} "
              f"pushed {days_since_push}d ago")

    with open(OUT, "w") as f:
        json.dump(records, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {len(records)} repo-enrichment records -> {OUT}")
    return 0 if records else 1


if __name__ == "__main__":
    sys.exit(main())
