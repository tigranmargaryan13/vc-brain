"""CLI: screen one founder through the fund's thesis.

    python -m sourcing.screen <github_handle> [thesis.json]

Scores the founder (same as `sourcing.score`) and then runs the Thesis Engine
over the result — showing whether they're on-thesis and the fund-specific
recommendation. Falls back to thesis.example.json / the built-in default when
no thesis file is given.
"""
from __future__ import annotations

import sys

from . import thesis as thesis_mod
from .founder_score import score_github_handle
from .github_collector import GitHubError
from .score import render


def render_fit(fit, thesis):
    lines = ["", f"  THESIS: {thesis.name}", "  " + "─" * 58]
    verdict_mark = {"ADVANCE": "✓ ADVANCE", "REVIEW": "~ REVIEW", "PASS": "✗ PASS"}
    lines.append(f"  Recommendation:  {verdict_mark.get(fit.verdict, fit.verdict)}")
    lines.append(f"  Thesis fit:      {fit.fit_score:.0f} / 100")
    lines.append(f"  Quality used:    {fit.quality_used:.0f}  "
                 f"(risk appetite: {thesis.risk_appetite}, bar {thesis.bar():.0f})")
    if fit.matched:
        lines.append("  Matched:")
        for m in fit.matched:
            lines.append(f"    ✓ {m}")
    if fit.flags:
        lines.append("  Flags:")
        for f in fit.flags:
            lines.append(f"    ⚠ {f}")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m sourcing.screen <github_handle> [thesis.json]", file=sys.stderr)
        return 2
    handle = argv[0].lstrip("@")
    thesis = thesis_mod.load(argv[1]) if len(argv) > 1 else thesis_mod.load_default()

    try:
        fs = score_github_handle(handle)
    except GitHubError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(render(fs))
    fit = thesis_mod.evaluate(thesis, fs)
    print(render_fit(fit, thesis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
