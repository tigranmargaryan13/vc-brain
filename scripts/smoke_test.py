# scripts/smoke_test.py — run: .venv/bin/python scripts/smoke_test.py
# Verifies every API connection we can reach with the credentials currently in .env.
# Safe to run repeatedly; skips (never fails) tests whose keys are missing.
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "fetchers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "resolver"))

import requests
from dotenv import load_dotenv

load_dotenv()

PASS, FAIL, SKIP = "✅ PASS", "❌ FAIL", "⏭  SKIP"
results = []

def record(name, status, detail=""):
    results.append((name, status, detail))
    print(f"{status}  {name}" + (f" — {detail}" if detail else ""))

def test_hn():
    from hn_fetcher import hn_signals_for_query
    res = hn_signals_for_query("Show HN AI")
    assert res["hits"], "no hits returned"
    record("HN (Algolia)", PASS, f"{len(res['hits'])} hits, no key needed")

def test_github():
    from github_fetcher import github_signals_for_username
    res = github_signals_for_username("octocat")
    assert res["repos"], "no repos returned"
    auth = "authenticated (5k req/hr)" if os.getenv("GITHUB_TOKEN") else "unauthenticated (60 req/hr)"
    record("GitHub", PASS, f"{len(res['repos'])} repos, {auth}")

def test_resolver():
    from resolver import resolve_identity
    merged = resolve_identity([
        {"name": "Jane Doe", "email": "jane@acme.ai", "github": "janedoe"},
        {"name": "jane doe", "website": "https://acme.ai", "twitter": "janedoe_ai"},
        {"name": "Bob Smith", "github": "bobsmith"},
    ])
    assert len(merged) == 2, f"expected 2 groups, got {len(merged)}"
    record("Resolver (dedup)", PASS, "3 signals -> 2 people")

def test_openai():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        record("OpenAI", SKIP, "OPENAI_API_KEY not in .env")
        return
    r = requests.get("https://api.openai.com/v1/models",
                     headers={"Authorization": f"Bearer {key}"}, timeout=15)
    r.raise_for_status()
    record("OpenAI", PASS, f"{len(r.json().get('data', []))} models visible")

def test_tavily():
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        record("Tavily", SKIP, "TAVILY_API_KEY not in .env")
        return
    r = requests.post("https://api.tavily.com/search",
                      headers={"Authorization": f"Bearer {key}"},
                      json={"query": "AI startup founder", "max_results": 3}, timeout=20)
    r.raise_for_status()
    record("Tavily", PASS, f"{len(r.json().get('results', []))} search results")

if __name__ == "__main__":
    for test in (test_hn, test_github, test_resolver, test_openai, test_tavily):
        try:
            test()
        except Exception as e:
            record(test.__name__.replace("test_", ""), FAIL, str(e))
    print()
    failed = [r for r in results if r[1] == FAIL]
    print(f"{len(results)} checks: "
          f"{sum(1 for r in results if r[1] == PASS)} passed, "
          f"{sum(1 for r in results if r[1] == SKIP)} skipped, {len(failed)} failed")
    sys.exit(1 if failed else 0)
