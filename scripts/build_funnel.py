"""Populate the Memory funnel from the bundled sources — no API keys required.

Scores ProductHunt founders (from producthunt_founder_signals.json, offline) and
Hacker News "Show HN" founders (public Algolia API) into data/. Add GitHub
founders too with:  python -m sourcing.analyze <handle>  (needs GITHUB_TOKEN;
OPENAI_API_KEY upgrades the capability read from heuristic to gpt-4o).

    python scripts/build_funnel.py
    scripts/serve.sh          # then serve the funnel to the UI
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sourcing.native_score import score_producthunt_signals
from sourcing.hn_source import collect_hn_founders

if __name__ == "__main__":
    ph = score_producthunt_signals(persist=True)
    print(f"  ProductHunt: scored {len(ph)} founders")
    hn = collect_hn_founders("AI", limit=8, persist=True)
    print(f"  Hacker News: scored {len(hn)} founders")
    print("  funnel populated → run `scripts/serve.sh`, then `python -m sourcing.store --thesis`")
