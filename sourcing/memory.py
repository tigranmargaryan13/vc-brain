"""Memory layer — append-only signal log. Nothing discarded.

Every scoring run appends (a) the raw signals it collected and (b) the scored
result to JSONL files under data/. Append-only by design: re-scoring a founder
later adds new rows rather than overwriting, so the store carries the trend over
time — the "Memory" pillar from docs/sourcing-architecture.md.

Stdlib only. JSONL keeps it literally "nothing discarded" and trivially
inspectable (`cat data/founder_scores.jsonl`); swap for SQLite when you want SQL.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(_ROOT, "data")
SIGNALS_PATH = os.path.join(DATA_DIR, "signals.jsonl")
SCORES_PATH = os.path.join(DATA_DIR, "founder_scores.jsonl")
SCREENS_PATH = os.path.join(DATA_DIR, "screens.jsonl")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _append(path, record):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _signals_from_profile(profile):
    """Normalize a GitHubProfile into individual timestamped, source-tagged signals."""
    ingested = _now()

    def sig(signal_type, payload, url=""):
        return {
            "entity": profile.handle,
            "source_id": "github",
            "signal_type": signal_type,
            "payload": payload,
            "url": url or profile.profile_url,
            "ingested_at": ingested,
        }

    sigs = [
        sig("account", {
            "name": profile.name,
            "bio": profile.bio,
            "followers": profile.followers,
            "account_age_days": profile.account_age_days,
            "owned_repo_count": len(profile.owned_repos),
        }),
        sig("activity", {
            "recent_push_events_90d": profile.recent_push_events,
            "active_repos_90d": profile.active_repos_90d,
        }),
    ]
    if profile.top_repo:
        r = profile.top_repo
        sigs.append(sig("repo", {
            "full_name": r.full_name,
            "description": r.description,
            "languages": list(r.languages.keys()),
            "size_kb": r.size_kb,
            "stars": r.stars,
            "forks": r.forks,
            "has_tests": r.has_tests,
            "has_ci": r.has_ci,
            "has_docs": r.has_docs,
        }, url=r.url))
    for org in profile.orgs:
        sigs.append(sig("org_membership", {"org": org}, url=f"https://github.com/{org}"))
    return sigs


def _score_record(fs):
    return {
        "entity": fs.handle,
        "name": fs.name,
        "profile_url": fs.profile_url,
        "score": round(fs.score, 1),
        "confidence": round(fs.confidence, 3),
        "band": [round(fs.band[0], 1), round(fs.band[1], 1)],
        "components": [
            {
                "name": c.name,
                "value": round(c.value, 1),
                "coverage": round(c.coverage, 3),
                "evidence": c.evidence,
            }
            for c in fs.components
        ],
        "capability_backend": fs.capability_detail.get("backend"),
        "capability_dimensions": fs.capability_detail.get("dimensions", {}),
        "attributes": fs.attributes,
        "scored_at": _now(),
    }


def persist(profile, founder_score):
    """Append this run's signals + score to the Memory store. Returns (n_signals)."""
    signals = _signals_from_profile(profile)
    for s in signals:
        _append(SIGNALS_PATH, s)
    _append(SCORES_PATH, _score_record(founder_score))
    return len(signals)


def load_scores():
    """All persisted score records, in write order (oldest first)."""
    if not os.path.exists(SCORES_PATH):
        return []
    out = []
    with open(SCORES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def count_signals():
    if not os.path.exists(SIGNALS_PATH):
        return 0
    with open(SIGNALS_PATH, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def latest_by_entity():
    """(latest_score_per_entity, run_count_per_entity) — the funnel view."""
    latest, counts = {}, {}
    for rec in load_scores():
        e = rec["entity"]
        latest[e] = rec  # newest wins (later lines overwrite)
        counts[e] = counts.get(e, 0) + 1
    return latest, counts


def latest_score(entity):
    """The most recent score record for one entity, or None."""
    found = None
    for rec in load_scores():
        if rec["entity"] == entity:
            found = rec
    return found


def latest_signals(entity):
    """Most recent payload of each signal_type for one entity: {signal_type: payload}.

    Lets downstream steps (memo, screening) reconstruct rich context straight from
    the Memory log — the point of "nothing discarded".
    """
    out, orgs = {}, []
    if not os.path.exists(SIGNALS_PATH):
        return out
    with open(SIGNALS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("entity") != entity:
                continue
            if rec["signal_type"] == "org_membership":
                orgs.append(rec["payload"].get("org"))
            else:
                out[rec["signal_type"]] = {**rec["payload"], "url": rec.get("url", "")}
    if orgs:
        out["orgs"] = orgs
    return out


def append_screen(record):
    _append(SCREENS_PATH, record)


def previous_screen(entity):
    """The most recent screen for one entity (before the current run) — for trend."""
    if not os.path.exists(SCREENS_PATH):
        return None
    found = None
    with open(SCREENS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if rec.get("entity") == entity:
                    found = rec
    return found
