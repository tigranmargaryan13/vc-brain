"""Native-signal Founder Score — score founders who have NO GitHub handle.

Maps platform-native signals (ProductHunt launches, organic upvotes, shipping
cadence, prior building, communication, team) onto the SAME coverage-weighted
Founder Score used for GitHub founders. So a non-technical / no-code founder is
still scored — on the same 0-100 axis, same components — and flows through
screening → thesis → memo → export unchanged. GitHub becomes one input, not the gate.

Signals map to the T1 criteria in vc_brain_criteria_and_schema.md. Absence of a
signal lowers that component's COVERAGE (widening the confidence band); it never
subtracts. Positive-only signals (serial founder, co-founder, tenure) never
penalize absence.
"""
from __future__ import annotations

import json

from .founder_score import Component, FounderScore, WEIGHTS, _aggregate, _clamp
from . import memory


def _v(signals, key, default=0):
    s = signals.get(key) or {}
    v = s.get("value")
    return default if v is None else v


def _cite(signals, key):
    return (signals.get(key) or {}).get("citation", "")


def _capability(signals):
    """Can they build & articulate? — prior shipped products + communication clarity."""
    prior = _v(signals, "prior_building_history", 0) or 0
    comm = _v(signals, "communication_text", {}) or {}
    desc = comm.get("description") or ""
    value = _clamp(30 + 8 * min(prior, 8) + (18 if len(desc) > 180 else 8 if desc else 0))
    ev = []
    built = (signals.get("prior_building_history") or {}).get("evidence") or []
    if built:
        ev.append(f"shipped {prior} product(s): {', '.join(built[:4])} — {_cite(signals, 'prior_building_history')}")
    coverage = 0.6 if prior else 0.3
    return Component("Capability", value, coverage, ev)


def _trajectory(signals):
    """Momentum — recent launch cadence + persistence."""
    cadence = _v(signals, "shipping_cadence_12mo", 0) or 0
    tenure = _v(signals, "building_tenure_days", 0) or 0
    value = _clamp(20 + 30 * min(cadence, 2) + (20 if tenure >= 365 else 10 if tenure >= 90 else 0))
    ev = []
    if cadence:
        ev.append(f"{cadence} launch(es) in the last 12 months — {_cite(signals, 'shipping_cadence_12mo')}")
    if tenure:
        ev.append(f"{tenure} days building publicly")
    coverage = 0.6 if cadence else 0.25
    return Component("Trajectory", value, coverage, ev)


def _traction(signals):
    """External validation — organic upvotes + early market engagement."""
    career = _v(signals, "earned_attention_career", 0) or 0
    peak = _v(signals, "earned_attention_peak", 0) or 0
    eng = _v(signals, "market_engagement", {}) or {}
    comments = eng.get("comments", 0) or 0
    value = _clamp(15 + career / 15 + comments / 2)
    ev = []
    if career:
        ev.append(f"{career} organic ProductHunt upvotes across launches (peak {peak}) — {_cite(signals, 'earned_attention_career')}")
    if comments:
        ev.append(f"{comments} launch comments (early demand signal)")
    coverage = min(1.0, (career + comments * 3) / 120)
    return Component("Traction", value, coverage, ev)


def _provenance(signals):
    """Track record & team — serial founder / co-founder present (both positive-only)."""
    serial = bool(_v(signals, "serial_founder", False))
    cofounder = bool(_v(signals, "co_founder_present", False))
    tenure = _v(signals, "building_tenure_days", 0) or 0
    value = _clamp((40 if serial else 20) + (25 if cofounder else 0) + (15 if tenure >= 365 else 0))
    ev = []
    if serial:
        ev.append(f"serial founder (>=2 lifetime launches) — {_cite(signals, 'serial_founder')}")
    if cofounder:
        team = (signals.get("co_founder_present") or {}).get("evidence") or []
        ev.append(f"paired team: {', '.join(team[:4])}")
    # Provenance from a single platform is a thin view of real network/pedigree.
    coverage = 0.4 if (serial or cofounder) else 0.15
    return Component("Provenance", value, coverage, ev)


# How the "earned attention" metric reads per source (for the memo/export).
_UNIT = {"producthunt": "ProductHunt upvotes", "hackernews": "HN points"}


def _attributes(founder, signals, source):
    domains = _v(signals, "domain_focus", []) or []
    comm = _v(signals, "communication_text", {}) or {}
    text = " ".join([
        founder.get("headline") or "", comm.get("tagline") or "",
        comm.get("description") or "", " ".join(domains),
    ]).lower()[:1000]
    career = _v(signals, "earned_attention_career", 0) or 0
    prior = _v(signals, "prior_building_history", 0) or 0
    stage = "early traction" if (career >= 800 or prior >= 4) else "pre-seed/idea"
    return {
        "location": "",            # native sources rarely expose location -> unknown, not penalized
        "languages": [],           # no code footprint
        "profile_text": text,      # feeds sector classification + thesis match
        "inferred_stage": stage,
        "stars": 0, "forks": 0, "followers": 0,
        # source-labelled native metrics, surfaced in the memo/export:
        "native_source": source,
        "native_unit": _UNIT.get(source, "upvotes"),
        "native_upvotes_career": career,
        "native_upvotes_peak": _v(signals, "earned_attention_peak", 0) or 0,
        "native_launches": prior,
        "native_cadence_12mo": _v(signals, "shipping_cadence_12mo", 0) or 0,
        "native_tenure_days": _v(signals, "building_tenure_days", 0) or 0,
        "serial_founder": bool(_v(signals, "serial_founder", False)),
        "co_founder_present": bool(_v(signals, "co_founder_present", False)),
        "domains": domains,
    }


def score_native(record, source="producthunt"):
    """Score one founder record from native signals. Returns a FounderScore."""
    founder = record.get("founder", {})
    signals = record.get("signals", {})
    handle = founder.get("username") or founder.get("name") or "unknown"
    components = [_capability(signals), _trajectory(signals), _traction(signals), _provenance(signals)]
    for c in components:                       # same power-law lens as GitHub founders
        c.weight = WEIGHTS.get(c.name, 1.0)
    score, confidence, band = _aggregate(components)
    return FounderScore(
        handle=handle,
        profile_url=founder.get("profile_url") or founder.get("ph_profile", ""),
        name=founder.get("name", handle),
        score=score, confidence=confidence, band=band,
        components=components,
        capability_detail={"backend": f"native:{source}", "dimensions": {}},
        attributes=_attributes(founder, signals, source),
    )


def _native_signals_for_memory(record):
    """Compact normalized signals for the Memory log (traceability)."""
    f, s = record.get("founder", {}), record.get("signals", {})
    launch = record.get("launch", {})
    out = [
        {"signal_type": "producthunt_profile",
         "payload": {"name": f.get("name"), "headline": f.get("headline"),
                     "product": launch.get("product"), "featured_at": launch.get("featured_at")},
         "url": f.get("ph_profile", "")},
        {"signal_type": "earned_attention",
         "payload": {"career": _v(s, "earned_attention_career", 0), "peak": _v(s, "earned_attention_peak", 0),
                     "current": _v(s, "earned_attention_current", 0)},
         "url": _cite(s, "earned_attention_career")},
        {"signal_type": "building",
         "payload": {"launches": _v(s, "prior_building_history", 0), "cadence_12mo": _v(s, "shipping_cadence_12mo", 0),
                     "tenure_days": _v(s, "building_tenure_days", 0), "serial": _v(s, "serial_founder", False)},
         "url": _cite(s, "prior_building_history")},
    ]
    return out


def score_producthunt_signals(path="producthunt_founder_signals.json", persist=True):
    """Score every founder in the PH signals JSON. Persists to Memory by default."""
    import os
    if not os.path.isabs(path):
        path = os.path.join(memory._ROOT, path)
    records = json.load(open(path, encoding="utf-8"))
    out = []
    for rec in records:
        fs = score_native(rec)
        if persist:
            memory.persist_native(fs, _native_signals_for_memory(rec))
        out.append(fs)
    return out
