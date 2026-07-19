"""Data-layer schema for the vibe-coding cold-start pipeline.

This module is where the brief's two NON-NEGOTIABLE rules live — in the data
layer, not bolted on at presentation time:

  Rule 1 — CLAIM WRAPPER. Every self-reported value is a `claim()` object
           {value, source, confidence, verified, contradicts[], extracted_at},
           never a bare value. This is what powers per-claim Trust Scores and
           contradiction flagging downstream.

  Rule 2 — ABSENCE ≠ NEGATIVE. A field we never observed is `unknown` (neutral,
           wide uncertainty); a field we checked and found genuinely empty is
           `confirmed-absent`. `field_state()` distinguishes the two so the
           scorer can widen the band on absence instead of punishing it.

It also defines the persistent entities from the brief schema:

  Founder  — persistent; the Founder/propensity Score lives here, never resets.
  Project  — per-opportunity; the 3 independent axes live here. Founder↔Project
             is MANY-TO-MANY and TIME-AWARE (a builder ships several projects;
             a project can be co-built), so the link is stored on BOTH sides
             (`founder.project_ids` / `project.founder_ids`) plus a timeline of
             timestamped `updates` — the substrate the persistence scorer reads.

Stdlib only, to match the rest of `sourcing/`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: str) -> str:
    """Deterministic id from natural keys — so re-ingesting the same profile
    doesn't fork a new entity (idempotent loads, reversible merges)."""
    h = hashlib.sha1("|".join(p.lower().strip() for p in parts if p).encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


# ── Rule 1: the claim wrapper ────────────────────────────────────────────────

def claim(value, source: str = "", confidence: float = 0.4,
          verified=None, contradicts=None, extracted_at: str | None = None) -> dict:
    """Wrap a self-reported value. Defaults are the honest ones for cold-start:
    confidence 0.4 (a founder's own word, unverified) and verified=None
    (unchecked — NOT False, which would mean we actively refuted it)."""
    return {
        "value": value,
        "source": source,
        "confidence": confidence,
        "verified": verified,                       # True observed · None unchecked · False conflicts
        "contradicts": list(contradicts or []),     # ids/labels of claims this conflicts with
        "extracted_at": extracted_at or now(),
    }


def observed(value, source: str = "") -> dict:
    """A value we saw directly at the source (a listed date, a live URL). Higher
    trust than a claim, but still carries provenance for traceability."""
    return claim(value, source=source, confidence=0.9, verified=True)


# ── Rule 2: absence handling ─────────────────────────────────────────────────

KNOWN, UNKNOWN, ABSENT = "known", "unknown", "confirmed-absent"


def field_state(value, checked_absent: bool = False) -> str:
    """known if we have a value; confirmed-absent only if we looked and it was
    genuinely empty; otherwise unknown. Never collapse unknown→absent."""
    if value not in (None, "", [], {}):
        return KNOWN
    return ABSENT if checked_absent else UNKNOWN


# ── provenance signal (every scored signal links back to its exact source) ───

def footprint_signal(signal_type: str, payload: dict, url: str,
                     observed_at: str | None = None, source_id: str = "madewithlovable") -> dict:
    """One entry in a founder's public_footprint. `url` is the exact page the
    signal came from — this is what makes 'click a signal → see the evidence' work."""
    return {
        "source_id": source_id,
        "signal_type": signal_type,       # "ship", "project_update", "monetization", "build_in_public", ...
        "payload": payload,
        "url": url,
        "observed_at": observed_at or now(),
    }


# ── entities ─────────────────────────────────────────────────────────────────

@dataclass
class Founder:
    """Persistent founder entity. Propensity Score attaches here later (D4)."""
    founder_id: str
    name: str
    handles: dict = field(default_factory=dict)          # {"x": "...", "github": "...", ...}
    source: str = ""
    profile_url: str = ""
    skills: list = field(default_factory=list)           # inferred from stack across projects
    public_footprint: list = field(default_factory=list) # list[footprint_signal] — provenance
    intent_signals: dict = field(default_factory=dict)   # {monetization_attempt: claim, ...} — cold-start edge
    prior_track_record: dict = field(default_factory=dict)
    project_ids: list = field(default_factory=list)       # many-to-many link (founder side)
    data_completeness: dict = field(default_factory=dict) # per-field: known/unknown/confirmed-absent
    founder_score: dict = field(default_factory=lambda: {"value": None, "trend": "new"})  # filled in D4


@dataclass
class Project:
    """Per-opportunity entity. The 3 independent axes attach here later (D4)."""
    startup_id: str
    name: str
    founder_ids: list = field(default_factory=list)       # many-to-many link (project side)
    slug: str = ""
    problem: dict = field(default_factory=dict)           # claim() — self-reported
    solution_description: dict = field(default_factory=dict)  # claim()
    product_link: str = ""
    provenance_url: str = ""
    categories: list = field(default_factory=list)
    stack: list = field(default_factory=list)
    first_seen: str = ""                                  # earliest observed ship/update date
    updates: list = field(default_factory=list)           # [{ts, kind, url}] — TIME-AWARE timeline
    traction_kpis: dict = field(default_factory=dict)      # {users: {claimed: claim, verified: ...}, ...}
    monetization: dict = field(default_factory=dict)       # {state, price, evidence} — toy→"a thing" tell
    startup_stage: str = "prototype"
    data_gaps: list = field(default_factory=list)          # explicit "not disclosed" markers
    # scored fields (independent, never averaged) — filled in D4:
    founder_axis: dict = field(default_factory=dict)
    market_axis: dict = field(default_factory=dict)
    idea_vs_market_axis: dict = field(default_factory=dict)
    trust_scores: list = field(default_factory=list)


def link(founder: Founder, project: Project) -> None:
    """Wire the many-to-many both ways (idempotent)."""
    if project.startup_id not in founder.project_ids:
        founder.project_ids.append(project.startup_id)
    if founder.founder_id not in project.founder_ids:
        project.founder_ids.append(founder.founder_id)
