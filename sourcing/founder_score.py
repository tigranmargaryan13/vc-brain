"""Founder Score — coverage-weighted, cold-start safe.

The one idea that makes this different from a filtered list: **absence of a
signal is not a penalty.** Each of the four components carries a value (0-100)
AND a coverage (0-1) — how much data actually backs it. The score is the
coverage-weighted mean, so a founder with a brilliant repo and nothing else
gets a high Capability score with a WIDE confidence band, rather than being
zeroed out for having no funding, no network, and no traction.

    score      = Σ(value_i · coverage_i) / Σ(coverage_i)
    confidence = f(total coverage, corroboration across components)

Every component cites the evidence that moved it (Trust Score / traceability).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import capability
from . import github_collector as gh
from . import memory


@dataclass
class Component:
    name: str
    value: float          # 0-100
    coverage: float       # 0-1  (how much data backs this)
    evidence: list = field(default_factory=list)  # ["<signal> — <url>"]
    note: str = ""


@dataclass
class FounderScore:
    handle: str
    profile_url: str
    name: str
    score: float                  # 0-100, coverage-weighted
    confidence: float             # 0-1
    band: tuple                   # (low, high) on the 0-100 scale
    components: list              # list[Component]
    capability_detail: dict       # raw output from the capability backend
    attributes: dict = field(default_factory=dict)  # location, languages, stage, text — for the Thesis Engine

    def band_str(self):
        return f"{self.band[0]:.0f}-{self.band[1]:.0f}"

    @classmethod
    def from_record(cls, rec):
        """Rebuild a FounderScore from a persisted Memory record (data/founder_scores.jsonl)."""
        components = [
            Component(c["name"], c["value"], c["coverage"], c.get("evidence", []))
            for c in rec.get("components", [])
        ]
        band = tuple(rec.get("band", [0.0, 100.0]))
        return cls(
            handle=rec["entity"],
            profile_url=rec.get("profile_url", ""),
            name=rec.get("name", rec["entity"]),
            score=rec.get("score", 0.0),
            confidence=rec.get("confidence", 0.0),
            band=band,
            components=components,
            capability_detail={
                "backend": rec.get("capability_backend"),
                "dimensions": rec.get("capability_dimensions", {}),
            },
            attributes=rec.get("attributes", {}),
        )


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _capability(profile):
    detail = capability.assess(profile.top_repo)
    repo = profile.top_repo
    evidence = []
    if repo:
        evidence.append(f"read repo {repo.full_name} — {repo.url}")
        # Coverage scales with how much real code we had to judge.
        vol = min(1.0, repo.size_kb / 800.0)          # ~800 KB reads as "substantial"
        files = min(1.0, len(repo.source_files) / 3.0)
        coverage = min(1.0, 0.35 + 0.4 * vol + 0.25 * files)
        note = f"backend={detail.get('backend')}"
    else:
        coverage = 0.0
        note = "no code found to assess"
    return Component("Capability", detail.get("score", 0), coverage, evidence, note), detail


def _trajectory(profile):
    pushes = profile.recent_push_events
    active = profile.active_repos_90d
    # Saturating value: sustained recent building reads high, one-off reads low.
    value = _clamp(pushes * 3 + active * 8)
    # Coverage: do we have enough activity history to judge momentum at all?
    signal_points = pushes + len(profile.owned_repos)
    coverage = min(1.0, signal_points / 6.0)
    evidence = []
    if pushes:
        evidence.append(f"{pushes} public push events in the last ~90 days — {profile.profile_url}")
    if active:
        evidence.append(f"{active} repo(s) pushed to in the last 90 days")
    note = "" if coverage > 0.15 else "little recent public activity"
    return Component("Trajectory", value, coverage, evidence, note)


def _provenance(profile):
    orgs = profile.orgs
    value = _clamp(len(orgs) * 25)
    # Deliberately degrades to ~0 coverage from GitHub alone — this is the
    # component that would be filled by the diaspora tracker / peer referrals.
    coverage = min(1.0, len(orgs) / 3.0)
    evidence = [f"member of org @{o}" for o in orgs[:5]]
    note = "no org/network signal (expected for cold-start; not penalized)" if not orgs else ""
    return Component("Provenance", value, coverage, evidence, note)


def _traction(profile):
    stars = sum(r.get("stargazers_count", 0) for r in profile.owned_repos)
    forks = sum(r.get("forks_count", 0) for r in profile.owned_repos)
    value = _clamp(stars * 2 + forks * 3)
    # Coverage low/zero for an unknown founder -> absence doesn't drag the score.
    coverage = min(1.0, (stars + forks) / 10.0)
    evidence = []
    if stars or forks:
        evidence.append(f"{stars} stars / {forks} forks across own projects")
    note = "no external engagement yet (absence flagged, not penalized)" if not (stars or forks) else ""
    return Component("Traction", value, coverage, evidence, note)


def _attributes(profile):
    """Candidate attributes the Thesis Engine reads: geography, tech signals, stage."""
    langs = list(profile.top_repo.languages.keys()) if profile.top_repo else []
    for r in profile.owned_repos:
        if r.get("language"):
            langs.append(r["language"])
    seen, langs_dedup = set(), []
    for l in langs:
        if l not in seen:
            seen.add(l)
            langs_dedup.append(l)

    texts = [profile.bio]
    if profile.top_repo:
        texts.append(profile.top_repo.description)
    for r in profile.owned_repos[:8]:
        if r.get("description"):
            texts.append(r["description"])
        texts.extend(r.get("topics") or [])
    profile_text = " ".join(t for t in texts if t).lower()[:1000]

    stars = sum(r.get("stargazers_count", 0) for r in profile.owned_repos)
    forks = sum(r.get("forks_count", 0) for r in profile.owned_repos)
    if stars >= 500 or forks >= 100:
        stage = "growth/traction"
    elif stars >= 20:
        stage = "early traction"
    else:
        stage = "pre-seed/idea"

    return {
        "location": profile.location or "",
        "languages": langs_dedup[:10],
        "profile_text": profile_text,
        "inferred_stage": stage,
        "stars": stars,
        "forks": forks,
        "followers": profile.followers,
        "owned_repo_count": len(profile.owned_repos),
        "recent_push_events": profile.recent_push_events,
    }


def _aggregate(components):
    totcov = sum(c.coverage for c in components)
    if totcov == 0:
        return 0.0, 0.10, (0.0, 100.0)
    score = sum(c.value * c.coverage for c in components) / totcov

    avg_cov = totcov / len(components)
    corroboration = sum(1 for c in components if c.coverage > 0.15)
    confidence = min(0.95, max(0.10, 0.25 + 0.55 * avg_cov + 0.05 * corroboration))

    # Wide band when data is thin; tight when corroborated across components.
    margin = (1 - confidence) * 35
    band = (_clamp(score - margin), _clamp(score + margin))
    return score, confidence, band


def score_github_handle(handle, persist=True):
    """End-to-end: collect -> score four components -> aggregate. Returns FounderScore.

    When persist=True (default), the raw signals and the scored result are
    appended to the Memory store (data/*.jsonl) so runs accumulate over time.
    """
    profile = gh.collect(handle)

    cap_component, cap_detail = _capability(profile)
    components = [
        cap_component,
        _trajectory(profile),
        _provenance(profile),
        _traction(profile),
    ]
    score, confidence, band = _aggregate(components)

    fs = FounderScore(
        handle=profile.handle,
        profile_url=profile.profile_url,
        name=profile.name,
        score=score,
        confidence=confidence,
        band=band,
        components=components,
        capability_detail=cap_detail,
        attributes=_attributes(profile),
    )
    if persist:
        memory.persist(profile, fs)
    return fs
