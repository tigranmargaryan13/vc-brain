"""Hacker News founder collector — "Show HN" launches as a native channel.

Groups Show HN posts by their author, derives the SAME native signals the scorer
consumes (earned attention = points, launches = Show HN count, cadence, tenure,
communication = titles), and scores each author with native_score. Fully public
Algolia API — no auth, no login, no ToS/scraping problem. Reuses the single HN
client in services/fetchers/hn_fetcher.py.

    python -m sourcing.hn_source [query] [--limit N]
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_ROOT, "services", "fetchers"))
from hn_fetcher import search_hackernews  # noqa: E402  — single HN Algolia client

from .native_score import score_native  # noqa: E402
from . import memory  # noqa: E402


def _sig(criterion, value, citation="", evidence=None, positive_only=False, axis="Founder"):
    return {criterion: {"criterion": criterion, "axis": axis, "tier": "T1",
                        "positive_only": positive_only, "value": value,
                        "citation": citation, "evidence": evidence}}


def _author_launches(author):
    """All Show HN posts by one author."""
    res = search_hackernews("", tags=f"show_hn,author_{author}")
    return [h for h in res.get("hits", []) if h.get("author") == author]


def _record(author, launches):
    launches = sorted(launches, key=lambda h: h.get("created_at_i") or 0)
    points = [h.get("points") or 0 for h in launches]
    comments = sum(h.get("num_comments") or 0 for h in launches)
    now = datetime.now(timezone.utc).timestamp()
    first_ts = launches[0].get("created_at_i") or now
    tenure_days = int((now - first_ts) / 86400)
    year_ago = now - 365 * 86400
    cadence = sum(1 for h in launches if (h.get("created_at_i") or 0) >= year_ago)
    latest = launches[-1]
    profile = f"https://news.ycombinator.com/user?id={author}"

    signals = {}
    signals.update(_sig("prior_building_history", len(launches), profile,
                        [h.get("title") for h in launches[:5]], positive_only=True))
    signals.update(_sig("serial_founder", len(launches) >= 2, profile, positive_only=True))
    signals.update(_sig("shipping_cadence_12mo", cadence, profile))
    signals.update(_sig("earned_attention_career", sum(points), profile))
    signals.update(_sig("earned_attention_peak", max(points) if points else 0, profile))
    signals.update(_sig("earned_attention_current", points[-1] if points else 0, latest.get("url") or profile))
    signals.update(_sig("building_tenure_days", tenure_days, profile, positive_only=True))
    signals.update(_sig("market_engagement", {"comments": comments, "reviews": 0, "rating": 0.0},
                        profile, axis="Idea-vs-Market"))
    signals.update(_sig("communication_text",
                        {"tagline": latest.get("title") or "", "description": "", "headline": ""},
                        latest.get("url") or profile))
    # domain_focus omitted — HN has no topic tags -> unknown, not penalized

    return {
        "founder": {"name": author, "username": author, "profile_url": profile,
                    "headline": latest.get("title") or "", "website": latest.get("url")},
        "launch": {"product": latest.get("title"), "url": latest.get("url"),
                   "featured_at": latest.get("created_at")},
        "signals": signals,
    }


def collect_hn_founders(query="", limit=8, persist=True):
    """Discover Show HN authors matching `query`, score each natively. Returns FounderScores."""
    res = search_hackernews(query, tags="show_hn")
    authors, seen = [], set()
    for h in res.get("hits", []):
        a = h.get("author")
        if a and a not in seen:
            seen.add(a)
            authors.append(a)
        if len(authors) >= limit:
            break

    out = []
    for a in authors:
        launches = _author_launches(a)
        if not launches:
            continue
        fs = score_native(_record(a, launches), source="hackernews")
        if persist:
            memory.persist_native(fs, [{
                "signal_type": "hn_launches",
                "payload": {"count": len(launches), "titles": [l.get("title") for l in launches[:5]]},
                "url": f"https://news.ycombinator.com/user?id={a}",
            }])
        out.append(fs)
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    query, limit = "", 8
    i = 0
    while i < len(argv):
        if argv[i] == "--limit":
            limit = int(argv[i + 1]); i += 2
        else:
            query = argv[i]; i += 1

    founders = collect_hn_founders(query, limit=limit)
    print(f"\n  HACKER NEWS — Show HN{f' matching {query!r}' if query else ''} → {len(founders)} founders scored\n")
    for fs in sorted(founders, key=lambda f: f.score, reverse=True):
        n = fs.attributes.get("native_launches", 0)
        up = fs.attributes.get("native_upvotes_career", 0)
        print(f"    {fs.score:5.1f} (band {fs.band_str()}) @{fs.handle:<18} {n} launch(es), {up} HN points")
    print("\n  → in the funnel:  python -m sourcing.store --thesis\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
