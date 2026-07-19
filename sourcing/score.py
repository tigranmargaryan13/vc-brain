"""CLI: score a founder from their GitHub handle.

    python -m sourcing.score <github_handle>

Prints the coverage-weighted Founder Score, the four-component breakdown with
evidence, and an honest confidence band. Runs with no dependencies and no auth;
set GITHUB_TOKEN (rate limit) and OPENAI_API_KEY (LLM code read) to upgrade.
"""
from __future__ import annotations

import sys

from .founder_score import score_github_handle
from .github_collector import GitHubError


def _bar(value, width=20):
    filled = int(round(value / 100 * width))
    return "█" * filled + "·" * (width - filled)


def _confidence_word(c):
    if c >= 0.7:
        return "high"
    if c >= 0.45:
        return "moderate"
    return "low"


def render(fs):
    lines = []
    lines.append("")
    lines.append(f"  FOUNDER SCORE — {fs.name}  (@{fs.handle})")
    lines.append(f"  {fs.profile_url}")
    lines.append("  " + "─" * 58)
    lines.append(f"  Score      {fs.score:5.1f} / 100   {_bar(fs.score)}")
    lines.append(
        f"  Confidence {_confidence_word(fs.confidence):>8}  "
        f"({fs.confidence:.0%})  →  likely range {fs.band_str()}"
    )
    lines.append("  " + "─" * 58)
    lines.append("  Components (value × coverage — absence widens the band, never subtracts)")
    lines.append("")
    for c in fs.components:
        cov_pct = f"{c.coverage:.0%}"
        lines.append(f"    {c.name:<12} {c.value:5.1f}  {_bar(c.value, 16)}  coverage {cov_pct:>4}")
        if c.note:
            lines.append(f"        └ {c.note}")
        for ev in c.evidence:
            lines.append(f"        • {ev}")
    # Capability rationale is the differentiator — surface it.
    detail = fs.capability_detail
    if detail.get("rationale"):
        lines.append("")
        lines.append("  Capability read:")
        for chunk in _wrap(detail["rationale"], 66):
            lines.append(f"    {chunk}")
        if detail.get("dimensions"):
            dims = "  ".join(f"{k}={v}" for k, v in detail["dimensions"].items())
            lines.append(f"    [{dims}]")
    lines.append("")
    return "\n".join(lines)


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m sourcing.score <github_handle>", file=sys.stderr)
        return 2
    handle = argv[0].lstrip("@")
    try:
        fs = score_github_handle(handle)
    except GitHubError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(render(fs))
    print("  saved to Memory (data/*.jsonl) — view with `python -m sourcing.store`\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
