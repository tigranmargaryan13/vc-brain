"""Cross-source identity resolution + merge.

The two scoring paths (GitHub `score_github_handle`, native `score_native`)
persist under different entity IDs, so one person can appear more than once in
the funnel (e.g. Manu Arora as a GitHub entity AND a ProductHunt entity). This
module resolves those into a single Founder — the persistent Founder entity from
the schema doc — and MERGES their signals into one unified, higher-coverage
score (GitHub capability read + ProductHunt/HN traction → tighter band than
either source alone). This is the "GitHub-as-additive-input" idea made real.

Cross-source linking is by shared handle where present, else fuzzy name (the
resolver's weakest link — fine for obvious dups, but real robustness needs
shared identifiers; we surface merged sources so it's auditable).
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_ROOT, "services", "resolver"))
from resolver import resolve_identity  # noqa: E402  — union-find dedup

from .founder_score import FounderScore, WEIGHTS, _aggregate  # noqa: E402


def _source_of(fs):
    b = (fs.capability_detail or {}).get("backend") or ""
    if b.startswith("native:"):
        return b.split(":")[1]
    if b.startswith("inbound:"):
        return "inbound-form"   # applied with no public code yet — scored on the form only
    return "github"             # incl. inbound applicants who gave a GitHub handle (scored via GH)


def _merge(fs_list):
    """Merge >=1 FounderScores for the SAME person into one unified score."""
    # GitHub first — its record has the LLM read + richest attributes.
    fs_list = sorted(fs_list, key=lambda f: 0 if _source_of(f) == "github" else 1)
    sources = sorted({_source_of(f) for f in fs_list})

    if len(fs_list) == 1:
        fs = fs_list[0]
        fs.attributes = {**fs.attributes, "sources": sources}
        return fs

    # Union of components by name, keeping the highest-coverage instance of each
    # (e.g. GitHub Capability from reading code beats a native proxy; native
    # Traction from upvotes beats GitHub stars when the founder has no repo stars).
    best = {}
    for fs in fs_list:
        for c in fs.components:
            if c.name not in best or c.coverage > best[c.name].coverage:
                best[c.name] = c
    components = list(best.values())
    for c in components:
        c.weight = WEIGHTS.get(c.name, c.weight)
    score, confidence, band = _aggregate(components)

    # Merge attributes: first non-empty wins (GitHub processed first).
    attrs = {}
    for fs in fs_list:
        for k, v in (fs.attributes or {}).items():
            if k not in attrs or (not attrs.get(k) and v):
                attrs[k] = v
    attrs["sources"] = sources
    attrs["merged_from"] = [f"{_source_of(f)}:{f.handle}" for f in fs_list]

    primary = fs_list[0]
    cap = {**(primary.capability_detail or {}), "backend": "merged:" + "+".join(sources)}
    return FounderScore(
        handle=primary.handle, profile_url=primary.profile_url, name=primary.name,
        score=score, confidence=confidence, band=band, components=components,
        capability_detail=cap, attributes=attrs,
        ambition_detail=getattr(primary, "ambition_detail", {}) or {},
    )


def resolve_and_merge(latest):
    """latest: {entity_id: score_record}. Returns merged FounderScores (deduped)."""
    candidates = []
    for entity, rec in latest.items():
        backend = rec.get("capability_backend") or ""
        source = backend.split(":")[1] if backend.startswith("native:") else "github"
        cand = {"name": (rec.get("name") or entity).strip(), "_entity": entity}
        if source == "github":
            cand["github"] = entity          # a real shared identifier when present
        candidates.append(cand)

    merged = []
    for group in resolve_identity(candidates):
        entities = [ev["_entity"] for ev in group["evidence"]]
        fs_list = [FounderScore.from_record(latest[e]) for e in entities]
        merged.append(_merge(fs_list))
    return merged
