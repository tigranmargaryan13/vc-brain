#!/usr/bin/env python3
"""Semantic Scholar sourcing channel — recent applied-AI papers with author-level
scholarly metrics (citations, h-index, output), mirroring the arXiv/ProductHunt
signals contract. Free Graph API, no key needed (S2_API_KEY honored if set —
unauthenticated pool rate-limits aggressively, so we retry with backoff and
tolerate partial results: a missing signal is unknown, never negative).

Run: .venv/bin/python scripts/fetch_semanticscholar_founders.py
Writes: semanticscholar_founder_signals.json (repo root)
"""
import json
import os
import sys
import time

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "semanticscholar_founder_signals.json")

SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
QUERIES = ["large language model agents", "AI infrastructure systems",
           "autonomous agents planning"]
FIELDS = ("title,url,publicationDate,citationCount,influentialCitationCount,"
          "externalIds,fieldsOfStudy,authors.name,authors.hIndex,"
          "authors.paperCount,authors.affiliations,authors.url")
MAX_AUTHORS = 12
MAX_COAUTHORS = 6
CORP_HINTS = ["inc", "labs", "research", "google", "meta", "microsoft", "amazon",
              "nvidia", "openai", "anthropic", "deepmind", "ibm", "apple", "bosch",
              "siemens", "samsung", "huawei", "bytedance", "gmbh", "ltd", "corp"]


def _sig(criterion, description, value, citation, evidence=None, positive_only=False):
    return {"criterion": criterion, "axis": "Founder", "tier": "T1",
            "positive_only": positive_only, "description": description,
            "value": value, "citation": citation, "evidence": evidence}


def s2_get(params):
    headers = {}
    if os.getenv("S2_API_KEY"):
        headers["x-api-key"] = os.environ["S2_API_KEY"]
    for wait in (0, 10, 30, 60):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(SEARCH, params=params, headers=headers, timeout=30)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code not in (429, 500, 502, 503):
            break
    return None


def main():
    records, seen = [], set()
    for q in QUERIES:
        if len(records) >= MAX_AUTHORS:
            break
        data = s2_get({"query": q, "year": "2026", "limit": 30, "fields": FIELDS})
        papers = (data or {}).get("data") or []
        print(f"query '{q}': {len(papers)} papers")
        for p in papers:
            if len(records) >= MAX_AUTHORS:
                break
            authors = p.get("authors") or []
            if not authors or len(authors) > MAX_COAUTHORS:
                continue
            first = authors[0]
            name = (first.get("name") or "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            url = p.get("url") or "https://www.semanticscholar.org"
            affs = first.get("affiliations") or []
            aff = affs[0] if affs else None

            signals = {
                "technical_output_paper": _sig(
                    "technical_output_paper",
                    "First-author applied-AI paper (Semantic Scholar search, 2026)",
                    1, url, [p.get("title")]),
                "coauthor_network": _sig(
                    "coauthor_network",
                    "Co-author count (small team = founder-shaped work)",
                    len(authors), url,
                    [a.get("name") for a in authors[1:4]] or None),
            }
            if p.get("citationCount") is not None:
                signals["earned_attention_citations"] = _sig(
                    "earned_attention_citations",
                    "Semantic Scholar citations for the seed paper "
                    f"(influential: {p.get('influentialCitationCount')})",
                    p["citationCount"], url)
            if first.get("hIndex") is not None:
                signals["author_h_index"] = _sig(
                    "author_h_index",
                    "Author h-index (Semantic Scholar) — sustained earned attention",
                    first["hIndex"], first.get("url") or url)
            if first.get("paperCount") is not None:
                signals["author_output_total"] = _sig(
                    "author_output_total",
                    "Author lifetime paper count (Semantic Scholar)",
                    first["paperCount"], first.get("url") or url)
            if aff and any(h in aff.lower() for h in CORP_HINTS):
                signals["industry_affiliation"] = _sig(
                    "industry_affiliation",
                    "Corporate/industry affiliation — market proximity",
                    aff, url, positive_only=True)

            arxiv_id = (p.get("externalIds") or {}).get("ArXiv")
            records.append({
                "channel": "semantic_scholar",
                "founder": {"name": name, "s2_url": first.get("url"),
                            "affiliation": aff},
                "paper": {"title": p.get("title"), "url": url,
                          "published": p.get("publicationDate"),
                          "arxiv_id": arxiv_id,
                          "fields": p.get("fieldsOfStudy")},
                "signals": signals,
            })
            print(f"  + {name} — h-index {first.get('hIndex')}, "
                  f"cites {p.get('citationCount')}, papers {first.get('paperCount')}")
        time.sleep(2)

    with open(OUT, "w") as f:
        json.dump(records, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {len(records)} author records -> {OUT}")
    return 0 if records else 1


if __name__ == "__main__":
    sys.exit(main())
