"""Front-end data layer — the API contract the UI binds to.

Turns everything in Memory into one structured, front-end-ready JSON: each
founder as a full decision packet (score, 3-axis screen, reference-class prior,
thesis verdict, evidence memo with per-claim Trust), plus categories/tags for
filtering and a funnel summary. Pure local transform — no GitHub/LLM calls, so
it's free to regenerate.

    python -m sourcing.export [output.json] [--thesis thesis.json]

Default output: data/frontend_data.json. Point it at the UI's public dir to
wire the front end, e.g.  python -m sourcing.export web/public/founders.json
"""
from __future__ import annotations

import json
import os
import sys

from . import memory
from . import memo as memo_mod
from . import reference_class as rc_mod
from . import screening
from . import thesis as thesis_mod
from .founder_score import FounderScore

DEFAULT_OUT = os.path.join(memory.DATA_DIR, "frontend_data.json")


# ---- serializers (dataclass -> plain JSON dict) ----

def _axis(a):
    return {
        "name": a.name, "rating": round(a.rating, 1), "stance": a.stance,
        "trend": a.trend, "confidence": round(a.confidence, 3),
        "rationale": a.rationale, "evidence": a.evidence,
    }


def _claim(c):
    return {
        "text": c.text, "status": c.status, "source": c.source,
        "trust": round(c.trust, 2), "trust_label": c.label,
        "verified": c.verified, "contradicts": c.contradicts,
    }


def _memo(m):
    return {
        "sections": [
            {"title": s.title, "claims": [_claim(c) for c in s.claims], "gaps": s.gaps}
            for s in m.sections
        ],
        "contradictions": m.contradictions,
        "data_completeness": m.completeness,
    }


def _tags(fs, screen, fit):
    tags = [fit.verdict.lower(), f"sector:{screen.sector}",
            f"founder:{screen.founder.stance}", f"market:{screen.market.stance}",
            f"idea:{screen.idea_vs_market.stance}"]
    stage = fs.attributes.get("inferred_stage")
    if stage:
        tags.append(f"stage:{stage}")
    if fs.confidence >= 0.7:
        tags.append("high-confidence")
    elif fs.confidence < 0.5:
        tags.append("low-confidence")
    if stage in ("pre-seed/idea", "early traction"):
        tags.append("cold-start")
    if any("geography off-thesis" in f for f in fit.flags):
        tags.append("off-thesis-geo")
    if any(c.coverage == 0 for c in fs.components):
        tags.append("has-data-gaps")
    return tags


def build_founder_view(record, thesis, source_track="outbound"):
    fs = FounderScore.from_record(record)
    signals = memory.latest_signals(fs.handle)
    screen = screening.screen_founder(fs, fs.attributes, persist=False)
    fit = thesis_mod.evaluate(thesis, fs)
    memo = memo_mod.build(fs, screen, signals, fit)
    rc = rc_mod.match(fs.attributes)

    return {
        "handle": fs.handle,
        "name": fs.name,
        "profile_url": fs.profile_url,
        "source_track": source_track,
        "funnel_status": "screened",
        "founder_score": {
            "value": round(fs.score, 1),
            "confidence": round(fs.confidence, 3),
            "band": [round(fs.band[0], 1), round(fs.band[1], 1)],
            "components": [
                {"name": c.name, "value": round(c.value, 1),
                 "coverage": round(c.coverage, 3), "evidence": c.evidence}
                for c in fs.components
            ],
        },
        "capability": fs.capability_detail,
        "sector": screen.sector,
        "screen": {
            "founder": _axis(screen.founder),
            "market": _axis(screen.market),
            "idea_vs_market": _axis(screen.idea_vs_market),
            "note": "three independent axes — not averaged",
        },
        "reference_class": {
            "similarity": rc.similarity, "best_archetype": rc.best_archetype,
            "matched_features": rc.matched_features, "resembles_count": rc.resembles_count,
            "caveat": rc.caveat, "kind": "soft prior — never a gate",
        },
        "thesis_fit": {
            "verdict": fit.verdict, "fit_score": round(fit.fit_score, 1),
            "quality_used": round(fit.quality_used, 1),
            "matched": fit.matched, "flags": fit.flags, "rationale": fit.rationale,
        },
        "memo": _memo(memo),
        "categories": {
            "verdict": fit.verdict,
            "sector": screen.sector,
            "stage": fs.attributes.get("inferred_stage", "unknown"),
            "source_track": source_track,
            "founder_stance": screen.founder.stance,
            "market_stance": screen.market.stance,
        },
        "tags": _tags(fs, screen, fit),
    }


def build_dataset(thesis=None):
    thesis = thesis or thesis_mod.load_default()
    latest, counts = memory.latest_by_entity()
    founders = [build_founder_view(rec, thesis) for rec in latest.values()]
    # Funnel order = thesis fit desc, then founder score desc.
    founders.sort(key=lambda v: (v["thesis_fit"]["fit_score"], v["founder_score"]["value"]), reverse=True)

    def _tally(key_path):
        out = {}
        for v in founders:
            k = v
            for p in key_path:
                k = k[p]
            out[k] = out.get(k, 0) + 1
        return out

    return {
        "generated_at": memory._now(),
        "thesis": {
            "name": thesis.name, "sectors": thesis.sectors,
            "geographies": thesis.geographies, "stages": thesis.stages,
            "risk_appetite": thesis.risk_appetite, "bar": thesis.bar(),
        },
        "summary": {
            "total_founders": len(founders),
            "scoring_runs": sum(counts.values()),
            "by_verdict": _tally(["thesis_fit", "verdict"]),
            "by_sector": _tally(["sector"]),
            "trust_legend": {
                "High": "observed from a primary source",
                "Med": "inferred or self-reported",
                "Low": "weak / unverified / conflicting",
                "gap": "explicitly not disclosed (not fabricated)",
            },
            "fairness": ("absence of a signal = unknown, never a penalty; pedigree/geography/age are "
                         "weak soft priors, never gates; reference class matches on demonstrated building, "
                         "not credentials; thesis geography is a fund mandate, not a quality judgement."),
        },
        "founders": founders,
    }


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    out_path, thesis_path = DEFAULT_OUT, None
    i = 0
    while i < len(argv):
        if argv[i] == "--thesis":
            thesis_path = argv[i + 1]
            i += 2
        else:
            out_path = argv[i]
            i += 1

    thesis = thesis_mod.load(thesis_path) if thesis_path else thesis_mod.load_default()
    data = build_dataset(thesis)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    s = data["summary"]
    print(f"\n  wrote {out_path}")
    print(f"  {s['total_founders']} founders · verdicts {s['by_verdict']} · sectors {s['by_sector']}")
    print(f"  thesis: {data['thesis']['name']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
