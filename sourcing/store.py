"""CLI: inspect the Memory store — what the system has collected so far.

    python -m sourcing.store                    # funnel: latest score per founder, ranked
    python -m sourcing.store <handle>           # score history (trend over time) for one founder
    python -m sourcing.store --thesis [path]    # rank the funnel through the fund's thesis lens
"""
from __future__ import annotations

import sys

from . import memory
from . import thesis as thesis_mod
from .founder_score import FounderScore


def show_funnel():
    latest, counts = memory.latest_by_entity()
    if not latest:
        print("Memory store is empty — run `python -m sourcing.score <handle>` first.")
        return
    runs = sum(counts.values())
    print(
        f"\n  MEMORY STORE — {len(latest)} founder(s), "
        f"{memory.count_signals()} signals, {runs} scoring run(s)"
    )
    print("  " + "─" * 62)
    print(f"  {'founder':<22}{'score':>7}{'band':>12}{'conf':>7}  runs")
    print("  " + "─" * 62)
    # Ranked by score descending — this is the sourcing funnel.
    for rec in sorted(latest.values(), key=lambda r: r["score"], reverse=True):
        band = f"{rec['band'][0]:.0f}-{rec['band'][1]:.0f}"
        print(
            f"  @{rec['entity']:<21}{rec['score']:>7.1f}{band:>12}"
            f"{rec['confidence'] * 100:>6.0f}%  {counts[rec['entity']]}"
        )
    print()


def show_history(handle):
    handle = handle.lstrip("@")
    recs = [r for r in memory.load_scores() if r["entity"] == handle]
    if not recs:
        print(f"No records for @{handle} yet.")
        return
    print(f"\n  @{handle} — {len(recs)} scoring run(s), oldest first")
    print("  " + "─" * 58)
    for r in recs:
        band = f"{r['band'][0]:.0f}-{r['band'][1]:.0f}"
        print(
            f"  {r['scored_at'][:19]}   score {r['score']:5.1f}   "
            f"band {band:>8}   conf {r['confidence'] * 100:3.0f}%   [{r['capability_backend']}]"
        )
    print()


def show_thesis_funnel(thesis_path=None):
    thesis = thesis_mod.load(thesis_path) if thesis_path else thesis_mod.load_default()
    latest, counts = memory.latest_by_entity()
    if not latest:
        print("Memory store is empty — run `python -m sourcing.score <handle>` first.")
        return
    rows = []
    for rec in latest.values():
        fit = thesis_mod.evaluate(thesis, FounderScore.from_record(rec))
        rows.append((rec, fit))
    # Rank by thesis fit, then verdict — this is the fund-specific funnel.
    order = {"ADVANCE": 0, "REVIEW": 1, "PASS": 2}
    rows.sort(key=lambda rf: (order.get(rf[1].verdict, 3), -rf[1].fit_score))

    print(f"\n  FUNNEL THROUGH THESIS — {thesis.name}")
    print(f"  (risk: {thesis.risk_appetite}, bar {thesis.bar():.0f} | "
          f"sectors: {', '.join(thesis.sectors) or 'any'} | geos: {', '.join(thesis.geographies) or 'any'})")
    print("  " + "─" * 70)
    print(f"  {'founder':<20}{'verdict':>9}{'fit':>6}{'score':>7}  matched / flags")
    print("  " + "─" * 70)
    for rec, fit in rows:
        note = "; ".join(fit.matched[:1] + fit.flags[:1]) or "—"
        print(f"  @{rec['entity']:<19}{fit.verdict:>9}{fit.fit_score:>6.0f}"
              f"{rec['score']:>7.1f}  {note[:34]}")
    print()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "--thesis":
        show_thesis_funnel(argv[1] if len(argv) > 1 else None)
    elif argv:
        show_history(argv[0])
    else:
        show_funnel()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
