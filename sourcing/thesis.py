"""Thesis Engine — the configurable fund lens.

The investor sets sectors, geography, stage, check size, ownership target, and
risk appetite; every candidate is then *filtered and scored through that lens*
(brief MVP #1 / FAQ #15 — configurable, never hardcoded to one fund).

The one non-obvious decision: **risk appetite decides how the confidence band
is read.** A conservative fund judges a founder on the band's LOWER bound
(uncertainty counts against you); an aggressive fund judges on the UPPER bound
(willing to bet on a thin-data cold-start founder); balanced uses the point
estimate. Same founder, different fund → different call. That's the point of
the pillar.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

# Keyword expansions so a thesis can say "AI infra" and match a founder whose
# repos never use that exact phrase. Unknown sectors fall back to their own words.
SECTOR_KEYWORDS = {
    "ai": ["ai", "ml", "machine learning", "deep learning", "llm", "neural",
           "inference", "model", "pytorch", "tensorflow", "transformer", "genai"],
    "ai infra": ["ai", "ml", "machine learning", "llm", "inference", "gpu",
                 "cuda", "vector", "embedding", "serving", "pytorch",
                 "tensorflow", "mlops", "kubernetes", "distributed", "model"],
    "developer tools": ["cli", "sdk", "devtools", "developer", "compiler",
                        "framework", "api", "library", "linter", "build", "ide"],
    "systems": ["kernel", "systems", "compiler", "runtime", "database",
                "networking", "rust", "c", "c++", "go", "distributed", "performance"],
    "fintech": ["payment", "payments", "bank", "banking", "finance", "fintech",
                "trading", "ledger", "wallet"],
    "security": ["security", "auth", "crypto", "encryption", "vulnerability",
                 "pentest", "infosec", "cyber"],
    "data": ["data", "etl", "pipeline", "warehouse", "analytics", "sql",
             "spark", "dbt", "streaming", "kafka"],
    "web3": ["blockchain", "web3", "ethereum", "solidity", "defi", "nft"],
}

_RISK_MIN_SCORE = {"conservative": 68.0, "balanced": 58.0, "aggressive": 48.0}


@dataclass
class Thesis:
    name: str
    sectors: list = field(default_factory=list)
    geographies: list = field(default_factory=list)
    stages: list = field(default_factory=list)
    check_size_usd: list = field(default_factory=list)   # [min, max] — informational (deal side)
    ownership_target_pct: float = 0.0                    # informational (deal side)
    risk_appetite: str = "balanced"
    min_score: float | None = None                       # derived from risk if unset

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d.get("name", "Untitled thesis"),
            sectors=d.get("sectors", []),
            geographies=d.get("geographies", []),
            stages=d.get("stages", []),
            check_size_usd=d.get("check_size_usd", []),
            ownership_target_pct=d.get("ownership_target_pct", 0.0),
            risk_appetite=d.get("risk_appetite", "balanced"),
            min_score=d.get("min_score"),
        )

    def bar(self):
        if self.min_score is not None:
            return self.min_score
        return _RISK_MIN_SCORE.get(self.risk_appetite, 58.0)


@dataclass
class ThesisFit:
    thesis_name: str
    fit_score: float          # 0-100, founder quality shaped by thesis dimensions
    verdict: str              # ADVANCE | REVIEW | PASS
    quality_used: float       # risk-adjusted founder quality (band bound or point)
    matched: list
    flags: list
    rationale: str


def load_default():
    """Load thesis.example.json from the repo root, or fall back to a built-in."""
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "thesis.example.json")
    if os.path.exists(path):
        return load(path)
    return Thesis.from_dict({
        "name": "Default — pre-seed AI infra / dev-tools (EU-leaning)",
        "sectors": ["AI infra", "developer tools", "systems"],
        "geographies": ["Europe", "London", "Berlin", "Amsterdam", "Paris", "Remote"],
        "stages": ["pre-seed", "seed"],
        "risk_appetite": "balanced",
    })


def load(path):
    with open(path, encoding="utf-8") as f:
        return Thesis.from_dict(json.load(f))


def _sector_keywords(sector):
    kws = SECTOR_KEYWORDS.get(sector.lower())
    if kws:
        return kws
    return [w for w in sector.lower().split() if len(w) > 2]


def _tokens(text):
    return set(re.findall(r"[a-z0-9+#.]+", text.lower()))


def _kw_hit(keywords, tokens, langs):
    for kw in keywords:
        if " " in kw:
            if kw in " ".join(tokens):   # multi-word: substring over the token stream
                return True
        elif kw in tokens or kw in langs:
            return True
    return False


def _geo_status(geographies, location):
    if not geographies:
        return "match"          # geo-agnostic thesis
    if not location:
        return "unknown"
    loc = location.lower()
    return "match" if any(g.lower() in loc for g in geographies) else "mismatch"


def evaluate(thesis, fs):
    """Score one FounderScore through the thesis lens. Returns ThesisFit."""
    attrs = getattr(fs, "attributes", {}) or {}
    tokens = _tokens(attrs.get("profile_text", ""))
    langs = [l.lower() for l in attrs.get("languages", [])]
    matched, flags = [], []

    # --- Sector fit (soft — overlap boosts, never zeroes) ---
    if thesis.sectors:
        hits = [s for s in thesis.sectors if _kw_hit(_sector_keywords(s), tokens, langs)]
        sector_fit = len(hits) / len(thesis.sectors)
        if hits:
            matched.append("sector: " + ", ".join(hits))
        else:
            flags.append("no sector overlap with thesis")
    else:
        sector_fit = 1.0
    sector_mult = 0.6 + 0.4 * sector_fit

    # --- Geography (hard-ish: explicit mismatch fails; unknown is flagged, not penalized) ---
    geo = _geo_status(thesis.geographies, attrs.get("location", ""))
    if geo == "match":
        matched.append(f"geography: {attrs.get('location') or 'in-mandate'}")
    elif geo == "mismatch":
        flags.append(f"geography off-thesis: {attrs.get('location')}")
    else:
        flags.append("geography unknown — verify")
    geo_mult = {"match": 1.0, "unknown": 0.9, "mismatch": 0.5}[geo]

    # --- Stage (weak GitHub signal → informational, mild effect only) ---
    stage = attrs.get("inferred_stage", "")
    stage_mult = 1.0
    if thesis.stages and stage:
        early = {"pre-seed/idea", "early traction"}
        wants_early = any(s.lower() in ("pre-seed", "seed") for s in thesis.stages)
        if wants_early and stage == "growth/traction":
            flags.append(f"stage may be late for thesis (inferred: {stage})")
            stage_mult = 0.85
        else:
            matched.append(f"stage (inferred): {stage}")

    # --- Founder quality through the RISK lens ---
    if thesis.risk_appetite == "conservative":
        quality = fs.band[0]      # lower bound — uncertainty counts against
        lens = "lower band bound (conservative)"
    elif thesis.risk_appetite == "aggressive":
        quality = fs.band[1]      # upper bound — bet on thin-data upside
        lens = "upper band bound (aggressive)"
    else:
        quality = fs.score
        lens = "point estimate (balanced)"

    fit_score = round(quality * geo_mult * sector_mult * stage_mult, 1)

    # --- Verdict ---
    bar = thesis.bar()
    if geo == "mismatch":
        verdict = "PASS"
    elif quality >= bar and fit_score >= 70:
        verdict = "ADVANCE"
    elif quality >= bar - 10 and fit_score >= 50:
        verdict = "REVIEW"
    else:
        verdict = "PASS"

    rationale = (
        f"{verdict} — fit {fit_score:.0f}/100. Founder quality {quality:.0f} "
        f"({lens}) vs bar {bar:.0f}. " + ("; ".join(matched) or "no thesis matches") + "."
    )
    return ThesisFit(thesis.name, fit_score, verdict, round(quality, 1), matched, flags, rationale)
