"""Bridge: ingestion (services/) → intelligence (sourcing/).

This is the seam that makes the two layers one system. It takes raw candidate
signals (from the fetchers), dedups them into unique people with the services
resolver, then runs each resolved GitHub identity through the intelligence
pipeline (score → screen → thesis → memo, via the Memory store).

    python -m sourcing.pipeline <github_handle> [<github_handle> ...]
    python -m sourcing.pipeline --producthunt [path.csv]   # load discovered founders from a dataset

Only THIS module bridges to services/, so it needs the services deps
(`pip install -r requirements.txt`); the rest of `sourcing/` stays stdlib-only.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in ("services/resolver", "services/fetchers"):
    sys.path.insert(0, os.path.join(_ROOT, _p))

from resolver import resolve_identity  # noqa: E402  — services entity resolver (dedup)

from .founder_score import score_github_handle  # noqa: E402
from .github_collector import GitHubError  # noqa: E402


def run(candidates):
    """candidates: raw signal dicts (name, github, twitter, linkedin, email, website).

    Returns (resolved_people, results) where results is [(person, FounderScore|None)].
    """
    people = resolve_identity(candidates)
    results = []
    for person in people:
        gh = person["handles"].get("github")
        if not gh:
            results.append((person, None))
            continue
        try:
            results.append((person, score_github_handle(gh)))
        except GitHubError:
            results.append((person, None))
    return people, results


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m sourcing.pipeline <github_handle> ... | --producthunt [path.csv]",
              file=sys.stderr)
        return 2

    if argv[0] == "--producthunt":
        from . import sources
        path = argv[1] if len(argv) > 1 else sources.PRODUCTHUNT_CSV
        candidates = sources.from_producthunt_csv(path)
        label = f"ProductHunt enriched dataset ({os.path.basename(path)})"
    else:
        candidates = [{"name": h.lstrip("@"), "github": h.lstrip("@")} for h in argv]
        label = "typed handles"

    people, results = run(candidates)
    scored = [(p, fs) for p, fs in results if fs]

    print(f"\n  INGEST → RESOLVE → SCORE   (source: {label})")
    print(f"  {len(candidates)} candidate(s) → {len(people)} resolved person(s) "
          f"→ {len(scored)} scored via GitHub\n")
    for person, fs in results:
        gh = person["handles"].get("github")
        names = ", ".join(person["names"]) or "?"
        if fs:
            print(f"    ✓ @{gh:<18} {names:<22} Founder Score {fs.score:5.1f}   band {fs.band_str()}")
        else:
            reason = "no GitHub handle" if not gh else "fetch failed"
            print(f"    · {('@'+gh) if gh else '(—)':<20} {names:<22} skipped ({reason})")
    print("\n  → scored candidates are in the Memory funnel:  python -m sourcing.store --thesis\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
