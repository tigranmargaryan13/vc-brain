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
from sourcing.inbound import score_application

# A couple of inbound applications (founders who applied) so the funnel is visibly
# TWO-SIDED — inbound + outbound — out of the box. No public code yet, so these
# score thin/honest (wide confidence band); an applicant who supplies a GitHub
# handle gets deep-read and scored on merit instead.
INBOUND_SEED = [
    {"name": "Jane Rivera", "company": "NoduleAI", "location": "Boston, MA",
     "one_liner": "An AI copilot for radiologists that flags missed lung nodules in chest CT scans",
     "industry": "healthcare AI", "stage": "pre-seed", "website": "https://noduleai.example"},
    {"name": "Diego Salas", "company": "LedgerLoop", "location": "Mexico City, MX",
     "one_liner": "Stablecoin payroll rails so LATAM startups can pay remote engineers in minutes, not weeks",
     "industry": "fintech / payments", "stage": "idea"},
]

if __name__ == "__main__":
    ph = score_producthunt_signals(persist=True)
    print(f"  ProductHunt: scored {len(ph)} founders")
    hn = collect_hn_founders("AI", limit=8, persist=True)
    print(f"  Hacker News: scored {len(hn)} founders")
    inb = [score_application(a, persist=True) for a in INBOUND_SEED]
    print(f"  Inbound:     scored {len(inb)} applicants (source_track=inbound)")
    print("  funnel populated → run `scripts/serve.sh`, then `python -m sourcing.store --thesis`")
