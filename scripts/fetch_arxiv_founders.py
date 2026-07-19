#!/usr/bin/env python3
"""arXiv sourcing channel — surface "pre-founding" technical founders from recent
applied-AI papers, mirroring the producthunt_founder_signals.json contract.

Rationale (see team research): most strong technical papers never become startups;
authors who ALSO release code show the openness/execution signals that predict
commercialization. We therefore seed from recent papers whose comments mention a
GitHub repo (arXiv `co:` field search), keep small-team papers, and build
per-first-author signal records with citations to the exact public source.

Signals per author (criterion contract: criterion/axis/tier/positive_only/
description/value/citation/evidence):
  technical_output_paper   — recent first-author applied-AI paper
  open_source_release      — code released with the paper (+only)
  publication_cadence_12mo — arXiv author-search paper count, last 12 months
  earned_attention_citations — Semantic Scholar citation count for the seed paper
  domain_focus             — arXiv categories
  coauthor_network         — co-author count (small team = founder-shaped)
  industry_affiliation     — corporate affiliation string when arXiv provides it (+only)

Identity caution: we NEVER assume the linked repo's owner is the author unless the
owner string contains the author's last name (avoids the benln->atom class of
misresolution). Otherwise the repo stays evidence, not an identity handle.

Run: .venv/bin/python scripts/fetch_arxiv_founders.py
Writes: arxiv_founder_signals.json (repo root)
"""
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "arxiv_founder_signals.json")

ARXIV_API = "http://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/arXiv:{aid}"
ATOM = "{http://www.w3.org/2005/Atom}"
ARX = "{http://arxiv.org/schemas/atom}"

CATEGORIES = ["cs.LG", "cs.AI", "cs.CL", "cs.RO", "cs.SE"]
MAX_SEED_PAPERS = 40
MAX_AUTHORS = 12
MAX_COAUTHORS = 6          # bias toward small-team (founder-shaped) papers
ARXIV_DELAY_S = 3          # arXiv API terms of use
CORP_HINTS = ["inc", "labs", "research", "google", "meta", "microsoft", "amazon",
              "nvidia", "openai", "anthropic", "deepmind", "ibm", "apple", "bosch",
              "siemens", "samsung", "huawei", "bytedance", "gmbh", "ltd", "corp"]
GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def _sig(criterion, description, value, citation, evidence=None, positive_only=False):
    return {"criterion": criterion, "axis": "Founder", "tier": "T1",
            "positive_only": positive_only, "description": description,
            "value": value, "citation": citation, "evidence": evidence}


def arxiv_query(search_query, max_results, sort=True):
    params = f"search_query={quote(search_query)}&start=0&max_results={max_results}"
    if sort:
        params += "&sortBy=submittedDate&sortOrder=descending"
    r = requests.get(f"{ARXIV_API}?{params}", timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    entries = []
    for e in root.findall(f"{ATOM}entry"):
        authors = []
        for a in e.findall(f"{ATOM}author"):
            name = a.findtext(f"{ATOM}name") or ""
            aff = a.findtext(f"{ARX}affiliation")
            authors.append({"name": name.strip(), "affiliation": (aff or "").strip() or None})
        aid = (e.findtext(f"{ATOM}id") or "").rsplit("/abs/", 1)[-1]
        entries.append({
            "arxiv_id": aid,
            "title": re.sub(r"\s+", " ", e.findtext(f"{ATOM}title") or "").strip(),
            "summary": re.sub(r"\s+", " ", e.findtext(f"{ATOM}summary") or "").strip(),
            "published": (e.findtext(f"{ATOM}published") or "")[:10],
            "comment": (e.findtext(f"{ARX}comment") or "").strip(),
            "categories": [c.get("term") for c in e.findall(f"{ATOM}category")],
            "authors": authors,
            "abs_url": f"https://arxiv.org/abs/{aid}",
        })
    return entries


def find_code_url(paper):
    m = GITHUB_RE.search(paper["comment"] + " " + paper["summary"])
    if not m:
        return None, None, None
    owner, repo = m.group(1), m.group(2).rstrip(".")
    return f"https://github.com/{owner}/{repo}", owner, repo


def author_cadence(name):
    """Papers by this author name in the last 12 months (arXiv au: search).
    Name-collision caveat is inherent — description of the signal says so."""
    url_q = f'au:"{name}"'
    try:
        entries = arxiv_query(url_q, 30)
    except Exception:
        return None, None
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    n = sum(1 for e in entries if e["published"] >= cutoff)
    search_url = f"https://arxiv.org/a/{quote(name)}" if False else \
        f"http://export.arxiv.org/api/query?search_query={quote(url_q)}"
    return n, search_url


def s2_citations(arxiv_id):
    try:
        r = requests.get(S2_API.format(aid=arxiv_id.split('v')[0]),
                         params={"fields": "citationCount,influentialCitationCount"}, timeout=20)
        if r.status_code != 200:
            return None
        d = r.json()
        return {"citations": d.get("citationCount"),
                "influential": d.get("influentialCitationCount"),
                "url": f"https://www.semanticscholar.org/arxiv/{arxiv_id.split('v')[0]}"}
    except Exception:
        return None


def main():
    cat_q = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    seed_q = f"({cat_q}) AND co:github"
    print(f"seed query: {seed_q}")
    papers = arxiv_query(seed_q, MAX_SEED_PAPERS)
    print(f"seed papers with code links: {len(papers)}")

    records, seen_authors = [], set()
    for p in papers:
        if len(records) >= MAX_AUTHORS:
            break
        if not p["authors"] or len(p["authors"]) > MAX_COAUTHORS:
            continue
        first = p["authors"][0]
        name = first["name"]
        if not name or name.lower() in seen_authors:
            continue
        code_url, owner, _repo = find_code_url(p)
        if not code_url:
            continue
        seen_authors.add(name.lower())

        # identity caution: only claim the GitHub handle if owner ~ author name
        last = name.split()[-1].lower()
        github_handle = owner if (owner and last and last in owner.lower()) else None

        time.sleep(ARXIV_DELAY_S)
        cadence, cadence_url = author_cadence(name)
        s2 = s2_citations(p["arxiv_id"])

        signals = {
            "technical_output_paper": _sig(
                "technical_output_paper",
                "First-author applied-AI paper on arXiv (recent submission window)",
                1, p["abs_url"], [p["title"]]),
            "open_source_release": _sig(
                "open_source_release",
                "Code released with the paper — openness/execution signal",
                True, p["abs_url"], [code_url], positive_only=True),
            "domain_focus": _sig(
                "domain_focus", "arXiv categories of the seed paper",
                p["categories"], p["abs_url"], None),
            "coauthor_network": _sig(
                "coauthor_network",
                "Co-author count on seed paper (small team = founder-shaped work)",
                len(p["authors"]), p["abs_url"],
                [a["name"] for a in p["authors"][1:4]] or None),
        }
        if cadence is not None:
            signals["publication_cadence_12mo"] = _sig(
                "publication_cadence_12mo",
                "arXiv author-name search: papers in the last 12 months "
                "(name-collision caveat applies)",
                cadence, cadence_url, None)
        if s2 and s2["citations"] is not None:
            signals["earned_attention_citations"] = _sig(
                "earned_attention_citations",
                "Semantic Scholar citation count for the seed paper "
                f"(influential: {s2['influential']})",
                s2["citations"], s2["url"], None)
        aff = first.get("affiliation")
        if aff and any(h in aff.lower() for h in CORP_HINTS):
            signals["industry_affiliation"] = _sig(
                "industry_affiliation",
                "Corporate/industry affiliation on the paper — market proximity",
                aff, p["abs_url"], None, positive_only=True)

        records.append({
            "founder": {
                "name": name,
                "affiliation": aff,
                "github": github_handle,
                "arxiv_author_search": cadence_url,
            },
            "paper": {
                "title": p["title"],
                "url": p["abs_url"],
                "arxiv_id": p["arxiv_id"],
                "published": p["published"],
                "categories": p["categories"],
                "code_url": code_url,
            },
            "signals": signals,
        })
        cites = s2["citations"] if s2 else "?"
        print(f"  + {name} — cadence {cadence}, citations {cites}, "
              f"gh={'@' + github_handle if github_handle else 'repo-only'}")

    with open(OUT, "w") as f:
        json.dump(records, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {len(records)} author records -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
