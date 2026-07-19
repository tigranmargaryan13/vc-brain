#!/usr/bin/env python3
"""OpenAlex sourcing channel — the API-accessible equivalent of Google Scholar
data (Scholar itself has no official API): recent applied-AI works with
author-level metrics (h-index, works count, citations) and institution types,
which give a clean industry-affiliation signal (type == "company").

Same signals contract as the arXiv / Semantic Scholar / ProductHunt channels.
Free API, no key. Docs: https://docs.openalex.org

Run: .venv/bin/python scripts/fetch_openalex_founders.py
Writes: openalex_founder_signals.json (repo root)
"""
import json
import os
import sys
import time

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "openalex_founder_signals.json")

WORKS = "https://api.openalex.org/works"
AUTHORS = "https://api.openalex.org/authors/"
SEARCHES = ["large language model agents", "AI systems infrastructure"]
SINCE = "2026-04-01"
MAX_AUTHORS = 12
MAX_COAUTHORS = 6


def _sig(criterion, description, value, citation, evidence=None, positive_only=False):
    return {"criterion": criterion, "axis": "Founder", "tier": "T1",
            "positive_only": positive_only, "description": description,
            "value": value, "citation": citation, "evidence": evidence}


def get(url, params=None):
    for wait in (0, 2, 6):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503):
                break
        except requests.RequestException:
            continue
    return None


def main():
    records, seen = [], set()
    for q in SEARCHES:
        if len(records) >= MAX_AUTHORS:
            break
        data = get(WORKS, {
            "search": q,
            "filter": f"from_publication_date:{SINCE},type:article",
            "per-page": 30,
            "select": "id,doi,display_name,publication_date,cited_by_count,"
                      "authorships,open_access,primary_topic",
        })
        works = (data or {}).get("results") or []
        print(f"search '{q}': {len(works)} works")
        for w in works:
            if len(records) >= MAX_AUTHORS:
                break
            ships = w.get("authorships") or []
            if not ships or len(ships) > MAX_COAUTHORS:
                continue
            first = next((a for a in ships if a.get("author_position") == "first"),
                         ships[0])
            name = ((first.get("author") or {}).get("display_name") or "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            work_url = w.get("doi") or w.get("id") or "https://openalex.org"
            insts = first.get("institutions") or []
            aff = insts[0]["display_name"] if insts else None
            company = next((i for i in insts if i.get("type") == "company"), None)

            # author-level metrics (h-index, output) — one extra call
            author_id = ((first.get("author") or {}).get("id") or "").rsplit("/", 1)[-1]
            adata = get(AUTHORS + author_id, {
                "select": "display_name,works_count,cited_by_count,summary_stats"}) \
                if author_id else None
            time.sleep(0.2)
            author_url = f"https://openalex.org/{author_id}" if author_id else work_url

            signals = {
                "technical_output_paper": _sig(
                    "technical_output_paper",
                    "First-author applied-AI work (OpenAlex search, recent)",
                    1, work_url, [w.get("display_name")]),
                "coauthor_network": _sig(
                    "coauthor_network",
                    "Co-author count (small team = founder-shaped work)",
                    len(ships), work_url,
                    [(a.get("author") or {}).get("display_name")
                     for a in ships[1:4]] or None),
            }
            if w.get("cited_by_count") is not None:
                signals["earned_attention_citations"] = _sig(
                    "earned_attention_citations",
                    "OpenAlex citations for the seed work",
                    w["cited_by_count"], work_url)
            if (w.get("open_access") or {}).get("is_oa"):
                signals["open_access_release"] = _sig(
                    "open_access_release",
                    "Work published open-access — openness signal",
                    True, work_url, positive_only=True)
            if adata:
                stats = adata.get("summary_stats") or {}
                if stats.get("h_index") is not None:
                    signals["author_h_index"] = _sig(
                        "author_h_index",
                        "Author h-index (OpenAlex) — sustained earned attention",
                        stats["h_index"], author_url)
                if adata.get("works_count") is not None:
                    signals["author_output_total"] = _sig(
                        "author_output_total",
                        "Author lifetime works count (OpenAlex)",
                        adata["works_count"], author_url)
                if adata.get("cited_by_count") is not None:
                    signals["author_citations_total"] = _sig(
                        "author_citations_total",
                        "Author lifetime citations (OpenAlex)",
                        adata["cited_by_count"], author_url)
            if company:
                signals["industry_affiliation"] = _sig(
                    "industry_affiliation",
                    "Institution of type 'company' on the work — market proximity",
                    company["display_name"], work_url, positive_only=True)
            elif aff:
                signals["institution"] = _sig(
                    "institution", "Author institution on the work",
                    aff, work_url)

            records.append({
                "channel": "openalex",
                "founder": {"name": name, "openalex_url": author_url,
                            "affiliation": aff},
                "paper": {"title": w.get("display_name"), "url": work_url,
                          "published": w.get("publication_date"),
                          "topic": (w.get("primary_topic") or {}).get("display_name")},
                "signals": signals,
            })
            h = (adata or {}).get("summary_stats", {}).get("h_index")
            print(f"  + {name} — h-index {h}, work cites {w.get('cited_by_count')}, "
                  f"company={'yes' if company else 'no'}")

    with open(OUT, "w") as f:
        json.dump(records, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {len(records)} author records -> {OUT}")
    return 0 if records else 1


if __name__ == "__main__":
    sys.exit(main())
