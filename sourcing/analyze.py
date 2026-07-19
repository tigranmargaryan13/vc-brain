"""CLI: full decision packet for a founder — the thing an investor acts on.

    python -m sourcing.analyze <handle> [thesis.json]
    python -m sourcing.analyze <handle> --from-memory   # rebuild from Memory, no GitHub calls

Pipeline: Founder Score -> Multi-Axis Screen (3 axes, not averaged) -> Thesis fit
-> Evidence-backed Investment Memo with per-claim Trust Scores.
"""
from __future__ import annotations

import sys

from . import memo as memo_mod
from . import memory
from . import outcome_prior as op_mod
from . import reference_class as rc_mod
from . import screening
from . import thesis as thesis_mod
from .founder_score import FounderScore, score_github_handle
from .github_collector import GitHubError

_TREND = {"improving": "↑ improving", "declining": "↓ declining", "stable": "→ stable", "new": "• new"}
_STANCE = {"bullish": "▲ bullish", "bear": "▼ bear", "neutral": "◆ neutral"}


def _axis_line(a):
    stance = _STANCE.get(a.stance, a.stance)
    return (f"    {a.name:<16} {a.rating:5.1f}/100   {stance:<12} "
            f"{_TREND.get(a.trend, a.trend):<12} conf {a.confidence:.0%}")


_VERIFIED = {True: "✓", False: "✗", None: "?"}


def _outcome_lines(op):
    """Render the Outcome Prior block (base-rate lift). Empty if no model is built."""
    if not op:
        return ["  OUTCOME PRIOR  (not available — run `python scripts/build_outcome_model.py`)", ""]
    L = ["  OUTCOME PRIOR  (base-rate lift vs a real denominator — soft, never a gate)"]
    L.append(f"    Resembles a proven founder: {op.score:.0f}/100   "
             f"(band {op.band[0]:.0f}-{op.band[1]:.0f}, conf {op.confidence:.0%})")
    L.append(f"    Base rate in cohort: {op.base_rate:.0f}/100  ·  "
             f"fit on {op.n_winners} proven vs {op.n_comparison} baseline builders")
    for d in op.drivers[:3]:
        sign = "▲" if d["contribution"] >= 0 else "▼"
        state = "has" if d["present"] else "lacks"
        L.append(f"      {sign} {state} {d['label']} (lift {d['lift']:.2f})")
    L.append(f"    ⚠ {op.caveat}")
    L.append("")
    return L


def render(fs, screen, fit, memo, thesis, rc, source_track="outbound", application_status="screened", op=None):
    L = []
    L.append("")
    L.append(f"  ═══ DECISION PACKET — {fs.name} (@{fs.handle}) ═══")
    L.append(f"  {fs.profile_url}    sector (inferred): {screen.sector}")
    L.append(f"  source: {source_track}-track   ·   funnel status: {application_status}")
    L.append("")
    L.append("  MULTI-AXIS SCREEN  (three independent axes — intentionally NOT averaged)")
    L.append(_axis_line(screen.founder))
    L.append(_axis_line(screen.market))
    L.append(_axis_line(screen.idea_vs_market))
    L.append(f"       └ founder: {screen.founder.rationale}")
    L.append(f"       └ market:  {screen.market.rationale}")
    L.append(f"       └ idea:    {screen.idea_vs_market.rationale}")
    L.append("")
    L.append("  REFERENCE-CLASS PRIOR  (soft — never a gate)")
    L.append(f"    Resembles: {rc.best_archetype} — {rc.similarity:.0f}% similarity "
             f"(materially resembles {rc.resembles_count} winner archetype(s))")
    L.append(f"    Matched on: {', '.join(rc.matched_features) or 'no features'}")
    L.append(f"    ⚠ {rc.caveat}")
    L.append("")
    L.extend(_outcome_lines(op))
    L.append(f"  THESIS: {thesis.name}")
    L.append(f"    {fit.verdict}  —  thesis fit {fit.fit_score:.0f}/100  "
             f"(risk: {thesis.risk_appetite}, bar {thesis.bar():.0f})")
    if fit.flags:
        L.append("    flags: " + "; ".join(fit.flags))
    L.append("")
    L.append("  ─── INVESTMENT MEMO (per-claim Trust Score · ✓ verified / ? unchecked / ✗ conflicts) ───")
    for sec in memo.sections:
        L.append(f"  {sec.title}")
        for c in sec.claims:
            line = f"    [{c.label:<4} {_VERIFIED[c.verified]}] {c.text}"
            if c.contradicts:
                line += f"   ⚠ contradicts: {'; '.join(c.contradicts)}"
            L.append(line)
        for g in sec.gaps:
            L.append(f"    [gap   ] {g}")
        L.append("")
    if memo.contradictions:
        L.append("  ⚠ CONTRADICTIONS FLAGGED:")
        for c in memo.contradictions:
            L.append(f"    • {c}")
        L.append("")
    comp = "   ".join(f"{k}={v}" for k, v in memo.completeness.items())
    L.append("  DATA COMPLETENESS (known / unknown / confirmed-absent):")
    L.append(f"    {comp}")
    L.append("")
    L.append("  FAIRNESS SAFEGUARDS: absence of a signal = unknown, never a penalty · pedigree, "
             "geography & age are weak soft priors, never gates · reference class matches on")
    L.append("    demonstrated building, not credentials · thesis geography is a fund mandate, not a quality judgement.")
    L.append("")
    L.append("  Trust: High = observed from a primary source · Med = inferred/self-reported · "
             "Low = weak/unverified/conflicting · gap = explicitly not disclosed (not fabricated).")
    L.append("")
    return "\n".join(L)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m sourcing.analyze <github_handle> [thesis.json] [--from-memory]",
              file=sys.stderr)
        return 2

    handle = argv[0].lstrip("@")
    rest = argv[1:]
    from_memory = "--from-memory" in rest
    thesis_path = next((a for a in rest if not a.startswith("--")), None)
    thesis = thesis_mod.load(thesis_path) if thesis_path else thesis_mod.load_default()

    if from_memory:
        rec = memory.latest_score(handle)
        if not rec:
            print(f"error: no Memory record for @{handle} — run `python -m sourcing.score {handle}` first.",
                  file=sys.stderr)
            return 1
        fs = FounderScore.from_record(rec)
    else:
        try:
            fs = score_github_handle(handle)   # collects + persists
        except GitHubError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    signals = memory.latest_signals(handle)
    screen = screening.screen_founder(fs, fs.attributes)
    fit = thesis_mod.evaluate(thesis, fs)
    memo = memo_mod.build(fs, screen, signals, fit)
    rc = rc_mod.match(fs.attributes)
    op = op_mod.try_predict(fs.attributes)               # base-rate lift (None if model not built)
    source_track = fs.attributes.get("source_track", "outbound")  # inbound applications carry "inbound"

    print(render(fs, screen, fit, memo, thesis, rc, source_track, op=op))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
