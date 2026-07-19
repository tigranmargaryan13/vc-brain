"""Outcome Prior — reference-class matching WITH a denominator (base-rate lift).

The next level up from `reference_class.py`. That module scores similarity to
winners; this one asks the predictive question: *how much more often did proven
founders have this feature than the typical sourced builder?* — which requires a
comparison cohort (the denominator the survivorship-bias trap is missing).

Two cohorts, both gathered the SAME way as sourcing (GitHub collector → attrs →
`reference_class.extract_features`):
  * winners     — a curated set of proven founders
  * comparison  — the typical sourced builder (our ProductHunt/HN funnel)

Per feature we fit a likelihood ratio, then combine with naive Bayes:

    LR(f)          = P(f | winner) / P(f | comparison)          # >1 predicts, ≈1 noise, <1 negative
    posterior_odds = prior_odds · Π LR(f present) · Π LR̄(f absent)
    P(resembles)   = posterior_odds / (1 + posterior_odds)

Honest by construction:
  * Features are demonstrated-building only (no schools/employers), so lift
    cannot encode a credential gate; every LR is surfaced so a bias proxy would
    be visible and removable (fairness audit).
  * Still a SOFT PRIOR, never a gate. Thin support → wide band, low confidence.
  * The label is "in the curated proven cohort vs the typical sourced builder",
    NOT ground-truth success — stated plainly. As Memory accrues real outcomes,
    refit on those and the prior sharpens (the flywheel).
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

from . import reference_class as rc

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "outcome_model.json")

CAVEAT = ("Soft prior, never a gate. Label = 'resembles a curated proven founder vs the typical "
          "sourced builder', not ground-truth success. Features are demonstrated-building only "
          "(no credentials), so lift cannot encode a pedigree gate. Thin samples → wide band; "
          "refit on real outcomes as Memory accrues them.")


def _clamp01(x):
    return max(0.0, min(1.0, x))


@dataclass
class FeatureLift:
    key: str
    label: str
    p_winner: float        # smoothed P(feature | winner)
    p_comparison: float    # smoothed P(feature | comparison)
    lift: float            # likelihood ratio when the feature is PRESENT
    lift_absent: float     # likelihood ratio when the feature is ABSENT
    support: int           # winners+comparison exhibiting it (drives band width)


@dataclass
class OutcomeModel:
    base_rate: float               # P(winner) in the combined cohort, 0-1
    n_winners: int
    n_comparison: int
    features: list                 # list[FeatureLift]
    built_at: str = ""

    def to_dict(self):
        return {
            "base_rate": self.base_rate,
            "n_winners": self.n_winners,
            "n_comparison": self.n_comparison,
            "built_at": self.built_at,
            "features": [f.__dict__ for f in self.features],
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            base_rate=d["base_rate"],
            n_winners=d["n_winners"],
            n_comparison=d["n_comparison"],
            built_at=d.get("built_at", ""),
            features=[FeatureLift(**f) for f in d["features"]],
        )


@dataclass
class OutcomePrior:
    probability: float             # 0-1 posterior "resembles a proven founder"
    score: float                   # 0-100 (probability * 100)
    band: tuple                    # (low, high) on 0-100
    base_rate: float               # 0-100, for reference ("lift over base")
    confidence: float              # 0-1
    drivers: list                  # [{label, present, lift, contribution}] sorted by |contribution|
    n_winners: int
    n_comparison: int
    caveat: str = CAVEAT


def fit(winners_feats, comparison_feats, ref=None, built_at=""):
    """winners_feats / comparison_feats: list of feature-sets (from extract_features)."""
    ref = ref or rc.load()
    labels = {f["key"]: f["label"] for f in ref["features"]}
    keys = [f["key"] for f in ref["features"]]

    W, C = len(winners_feats), len(comparison_feats)
    feats = []
    for k in keys:
        w = sum(1 for s in winners_feats if k in s)
        c = sum(1 for s in comparison_feats if k in s)
        p_w = (w + 1) / (W + 2)          # Laplace smoothing — 3-of-3 winners ≠ infinite lift
        p_c = (c + 1) / (C + 2)
        feats.append(FeatureLift(
            key=k, label=labels.get(k, k),
            p_winner=round(p_w, 4), p_comparison=round(p_c, 4),
            lift=round(p_w / p_c, 3),
            lift_absent=round((1 - p_w) / (1 - p_c), 3),
            support=w + c,
        ))
    base_rate = W / (W + C) if (W + C) else 0.0
    return OutcomeModel(round(base_rate, 4), W, C, feats, built_at)


def predict(attrs, model):
    """Score one candidate's attributes against a fitted model → OutcomePrior."""
    cand = rc.extract_features(attrs)

    # Prior odds of being in the winners cohort (smoothed so a cohort edge can't blow up).
    prior_odds = (model.n_winners + 1) / (model.n_comparison + 1)
    log_odds = math.log(prior_odds)

    drivers, present_supports = [], []
    for f in model.features:
        present = f.key in cand
        lr = f.lift if present else f.lift_absent
        contribution = math.log(lr) if lr > 0 else 0.0
        log_odds += contribution
        if present:
            present_supports.append(f.support)
        drivers.append({
            "label": f.label, "present": present,
            "lift": f.lift if present else round(f.lift_absent, 3),
            "contribution": round(contribution, 4),
        })

    odds = math.exp(log_odds)
    p = _clamp01(odds / (1 + odds))

    # Band + confidence from the weakest evidence link: the smallest sample backing
    # a feature the candidate actually has (few present → lean on total cohort size).
    min_support = min(present_supports) if present_supports else (model.n_winners + model.n_comparison)
    se = 1.0 / math.sqrt(min_support + 2)
    band = (round(_clamp01(p - se) * 100, 1), round(_clamp01(p + se) * 100, 1))
    confidence = round(max(0.15, min(0.9, 1 - 2 * se)), 3)

    drivers.sort(key=lambda d: abs(d["contribution"]), reverse=True)
    return OutcomePrior(
        probability=round(p, 4),
        score=round(p * 100, 1),
        band=band,
        base_rate=round(model.base_rate * 100, 1),
        confidence=confidence,
        drivers=drivers,
        n_winners=model.n_winners,
        n_comparison=model.n_comparison,
    )


def save(model, path=MODEL_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model.to_dict(), f, ensure_ascii=False, indent=2)


def load_model(path=MODEL_PATH):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return OutcomeModel.from_dict(json.load(f))


def try_predict(attrs, path=MODEL_PATH):
    """Convenience for the pipeline: predict if a model exists, else None."""
    model = load_model(path)
    return predict(attrs, model) if model else None
