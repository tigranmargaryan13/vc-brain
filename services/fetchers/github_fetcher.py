"""GitHub fetcher — ingestion-layer adapter.

Consolidated: the single GitHub HTTP client lives in `sourcing.github_collector`
(stdlib urllib, GITHUB_TOKEN-aware, also does the deep read for scoring). This
module is the thin ingestion adapter that turns a username into flat repo
signals for the raw-signals store, so there is exactly ONE GitHub client.
"""
import os
import sys
from datetime import datetime

# Make the `sourcing` package importable regardless of how this is launched
# (smoke_test puts services/fetchers on sys.path but not the repo root).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sourcing.github_collector import public_repos  # noqa: E402  (single GitHub client)


def github_signals_for_username(username):
    repos = public_repos(username)
    signals = [
        {
            "repo": r["name"],
            "full_name": r["full_name"],
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "language": r.get("language"),
            "updated_at": r["updated_at"],
            "html_url": r["html_url"],
        }
        for r in repos
    ]
    return {"username": username, "fetched_at": datetime.utcnow().isoformat(), "repos": signals}


if __name__ == "__main__":
    print(github_signals_for_username("octocat"))
