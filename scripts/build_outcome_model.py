"""Build the Outcome Prior model from real cohorts, gathered the SAME way as sourcing.

    python scripts/build_outcome_model.py

Winners come from data/outcome_cohort.json (curated proven founders); the
comparison cohort (the denominator) is pulled live from the ProductHunt sourcing
dataset. Both are run through the exact collector + feature extractor the live
pipeline uses, so the fitted lift is apples-to-apples. Writes data/outcome_model.json.

No LLM and no scoring here — we only need each person's public attributes to
extract the demonstrated-building features, so it's cheap and fast.
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from sourcing import github_collector as gh          # noqa: E402
from sourcing import outcome_prior                     # noqa: E402
from sourcing import reference_class as rc             # noqa: E402
from sourcing import sources                           # noqa: E402
from sourcing.founder_score import _attributes         # noqa: E402

COHORT_PATH = os.path.join(_ROOT, "data", "outcome_cohort.json")


def _features_for(handle):
    """Collect one handle the same way the pipeline does → demonstrated-building features."""
    profile = gh.collect(handle)
    return rc.extract_features(_attributes(profile))


def _gather(handles, label):
    feats, ok = [], []
    for h in handles:
        try:
            feats.append(_features_for(h))
            ok.append(h)
            print(f"    ✓ {label}: @{h}")
        except Exception as e:                          # 404 / rate limit / parse — skip, keep going
            print(f"    · {label}: @{h} skipped ({type(e).__name__})")
    return feats, ok


def _comparison_handles(cfg):
    """The denominator: a curated baseline of typical active builders, plus real
    github handles from the ProductHunt sourcing funnel. Outcome unlabeled."""
    handles, seen = [], set()
    for h in cfg.get("comparison_handles", []):          # curated baseline builders
        if h and h.lower() not in seen:
            seen.add(h.lower())
            handles.append(h)
    for c in sources.from_producthunt_csv():             # real sourced candidates
        h = c.get("github")
        if h and h.lower() not in seen:
            seen.add(h.lower())
            handles.append(h)
    return handles[: cfg.get("comparison_max", 24)]


def main():
    with open(COHORT_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    print("\n  BUILDING OUTCOME PRIOR MODEL  (base-rate lift over a real denominator)\n")
    print("  Winners (curated proven founders):")
    win_feats, win_ok = _gather(cfg["winners"], "winner")

    print("\n  Comparison (typical sourced builder — ProductHunt funnel):")
    cmp_feats, cmp_ok = _gather(_comparison_handles(cfg), "compare")

    if len(win_feats) < 3 or len(cmp_feats) < 3:
        print(f"\n  ✗ Not enough data (winners={len(win_feats)}, comparison={len(cmp_feats)}). "
              "Need ≥3 each. Check network / GITHUB_TOKEN.", file=sys.stderr)
        return 1

    model = outcome_prior.fit(win_feats, cmp_feats)
    outcome_prior.save(model)

    print(f"\n  ✓ Fitted on {model.n_winners} winners vs {model.n_comparison} comparison "
          f"(base rate {model.base_rate:.0%}). Wrote data/outcome_model.json\n")
    print("  Per-feature lift (LR>1 = enriched in proven founders):")
    for fl in sorted(model.features, key=lambda x: x.lift, reverse=True):
        print(f"    {fl.label:<32} lift {fl.lift:>5.2f}   "
              f"(winners {fl.p_winner:.0%} vs comparison {fl.p_comparison:.0%}, n={fl.support})")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
