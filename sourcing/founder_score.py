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

from . import ambition
from . import capability
from . import github_collector as gh
from . import memory

# Power-law weights (brief open-decision #2): not every criterion matters equally
# for a "next 3 unicorns" fund. Weight tunes a component's PULL on the score; it
# does NOT touch confidence (that stays a pure function of how much data we have).
# Upweighted: demonstrated capability, ceiling/potential, and the cold-start intent
# edge. Downweighted: provenance (network) — leaning on it rebuilds the network gate.
WEIGHTS = {
    "Capability": 1.3,
    "Ceiling": 1.5,
    "Intent": 1.2,
    "Skills": 1.0,
    "Trajectory": 1.0,
    "Traction": 1.0,
    "Provenance": 0.8,
}


@dataclass
class Component:
    name: str
    value: float          # 0-100
    coverage: float       # 0-1  (how much data backs this)
    evidence: list = field(default_factory=list)  # ["<signal> — <url>"]
    note: str = ""
    weight: float = 1.0   # power-law pull on the score (see WEIGHTS); never affects confidence


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
    ambition_detail: dict = field(default_factory=dict)  # raw output from the ceiling/ambition backend

    def band_str(self):
        return f"{self.band[0]:.0f}-{self.band[1]:.0f}"

    @classmethod
    def from_record(cls, rec):
        """Rebuild a FounderScore from a persisted Memory record (data/founder_scores.jsonl)."""
        components = [
            Component(c["name"], c["value"], c["coverage"], c.get("evidence", []),
                      c.get("note", ""), c.get("weight", WEIGHTS.get(c["name"], 1.0)))
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
            ambition_detail=rec.get("ambition_detail", {}),
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


def _distinct_languages(profile):
    langs = list(profile.top_repo.languages.keys()) if profile.top_repo else []
    langs += [r["language"] for r in profile.owned_repos if r.get("language")]
    seen, out = set(), []
    for l in langs:
        if l and l not in seen:
            seen.add(l)
            out.append(l)
    return out


def _skills(profile):
    """Demonstrated skills — read from shipped code, not claimed on a profile.

    Technical breadth only for now (languages actually used); commercial/domain
    skills are T2 (post-conversion) per the criteria doc, so their absence here
    just leaves coverage partial rather than penalizing.
    """
    langs = _distinct_languages(profile)
    breadth = len(langs)
    value = _clamp(30 + 12 * breadth)          # more distinct, shipped languages -> broader demonstrated skill
    coverage = min(1.0, breadth / 4.0)
    evidence = [f"technical skills demonstrated in shipped code: {', '.join(langs[:8])}"] if langs else []
    note = ("technical only; commercial/domain skills validated post-conversion (T2)"
            if langs else "no demonstrated technical skill yet (unknown, not penalized)")
    return Component("Skills", value, coverage, evidence, note)


# Positive-only intent tells — the cold-start edge (criteria doc §Intent signals).
# Presence scores UP; absence just leaves coverage low, NEVER subtracts.
_INTENT_PHRASES = {
    "stealth/building tell": (
        "stealth", "building something", "working on something new", "new venture",
        "0 to 1", "0->1", "coming soon", "currently building", "wip",
    ),
    "fresh landing / waitlist": (
        "waitlist", "early access", "join the beta", "get early access", "sign up for",
    ),
    "problem obsession": (
        "obsessed with", "i keep thinking about", "why is there no", "the problem with",
    ),
}


def _intent(profile):
    """Detect 'becoming a founder' behavior before the title exists. `[+only]`."""
    texts = [profile.bio]
    if profile.top_repo:
        texts += [profile.top_repo.description, profile.top_repo.readme[:1500]]
    for r in profile.owned_repos[:10]:
        if r.get("description"):
            texts.append(r["description"])
    blob = " ".join(t for t in texts if t).lower()

    tells = []
    for label, phrases in _INTENT_PHRASES.items():
        hit = next((p for p in phrases if p in blob), None)
        if hit:
            tells.append(f"{label} — matched \"{hit}\"")
    # Structural tells (no text needed): blank bio + active building reads as a
    # post-departure stealth signal; prolific shipping reads as unmonetized building.
    if not profile.bio and profile.recent_push_events >= 5:
        tells.append("blank bio while actively shipping — possible post-departure/stealth")
    if len(profile.owned_repos) >= 6 and profile.recent_push_events >= 5:
        tells.append("ships repeatedly with no commercial framing — unmonetized building")

    value = _clamp(35 * len(tells))            # each independent tell adds signal; capped at 100
    coverage = min(1.0, len(tells) / 2.0)      # 2+ tells = fully covered; 0 tells = 0 (not a penalty)
    note = "no intent tells surfaced (expected pre-departure; not penalized)" if not tells else ""
    return Component("Intent", value, coverage, tells, note)


def _ceiling(profile):
    """Ceiling / potential — how big and original the thing they're pointed at is."""
    detail = ambition.assess(profile)
    text_len = len(ambition.build_text(profile))
    if text_len == 0:
        return Component("Ceiling", 0, 0.0, [], "no public text to judge ambition (unknown)"), detail
    # Coverage scales with how much of the founder's own writing we had to read.
    coverage = min(1.0, 0.3 + text_len / 2000.0)
    evidence = [detail.get("rationale", "")] if detail.get("rationale") else []
    note = f"backend={detail.get('backend')}"
    return Component("Ceiling", detail.get("score", 0), coverage, evidence, note), detail


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
        "account_age_days": profile.account_age_days,   # building-tenure proxy (not pedigree)
    }


def _aggregate(components):
    # Score = coverage- AND weight-weighted mean. Coverage keeps it cold-start safe
    # (thin data widens the band, never subtracts); weight applies the power-law lens.
    wcov = sum(c.coverage * c.weight for c in components)
    if wcov == 0:
        return 0.0, 0.10, (0.0, 100.0)
    score = sum(c.value * c.coverage * c.weight for c in components) / wcov

    # Confidence is a pure function of DATA density — weights must not inflate it.
    totcov = sum(c.coverage for c in components)
    avg_cov = totcov / len(components)
    corroboration = sum(1 for c in components if c.coverage > 0.15)
    confidence = min(0.95, max(0.10, 0.25 + 0.55 * avg_cov + 0.04 * corroboration))

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
    ceiling_component, amb_detail = _ceiling(profile)
    components = [
        cap_component,
        _skills(profile),
        _trajectory(profile),
        ceiling_component,
        _intent(profile),
        _provenance(profile),
        _traction(profile),
    ]
    for c in components:                       # apply the power-law weights (open-decision #2)
        c.weight = WEIGHTS.get(c.name, 1.0)
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
        ambition_detail=amb_detail,
    )
    if persist:
        memory.persist(profile, fs)
    return fs
