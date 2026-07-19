"""Evidence-Backed Investment Memo + Trust Score (brief MVP #7 + Appendix 1).

Every claim traces to evidence and carries its own Trust Score — Trust is
PER CLAIM, not one number for the company (FAQ #7). Claims are built from
collected signals, so nothing is fabricated; where a data point is missing it
is flagged explicitly ("Cap table: not disclosed") rather than guessed — which
the brief scores as *more* trustworthy, not less (FAQ #9).

Required sections (Appendix 1): Company snapshot, Investment hypotheses, SWOT,
Problem & product, Traction & KPIs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# How much to trust a claim, by how we know it.
STATUS_TRUST = {
    "observed": 0.9,        # a primary source states it directly (GitHub star count, languages)
    "inferred": 0.55,       # derived by us (sector, stage)
    "self-reported": 0.4,   # the founder's own words (bio/README) — unverified
    "contradiction": 0.25,  # conflicts with other evidence
}


def _label(trust):
    return "High" if trust >= 0.75 else "Med" if trust >= 0.5 else "Low"


# verified: True = we observed/corroborated it directly; None = unchecked; False = conflicts.
_STATUS_VERIFIED = {"observed": True, "inferred": None, "self-reported": None, "contradiction": False}


@dataclass
class Claim:
    text: str
    status: str
    source: str = ""
    contradicts: list = field(default_factory=list)   # texts of claims this conflicts with

    @property
    def trust(self):
        t = STATUS_TRUST.get(self.status, 0.4)
        return min(t, 0.3) if self.contradicts else t   # a contradiction caps trust low

    @property
    def label(self):
        return _label(self.trust)

    @property
    def verified(self):
        return _STATUS_VERIFIED.get(self.status)


@dataclass
class Section:
    title: str
    claims: list = field(default_factory=list)   # list[Claim]
    gaps: list = field(default_factory=list)      # explicitly-flagged missing data


@dataclass
class Memo:
    handle: str
    name: str
    sections: list           # list[Section]
    contradictions: list     # flagged before they reach the investor
    completeness: dict = field(default_factory=dict)  # field -> known | unknown | confirmed-absent


def _fmt_int(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def build(fs, screen, signals, thesis_fit=None):
    """Assemble the memo from the scored founder, the 3-axis screen, and Memory signals."""
    attrs = fs.attributes or {}
    repo = signals.get("repo", {})
    account = signals.get("account", {})
    activity = signals.get("activity", {})

    repo_stars = repo.get("stars", 0)                       # the one named repo
    total_stars = attrs.get("stars") or repo_stars          # summed across own projects
    total_forks = attrs.get("forks") or repo.get("forks", 0)
    followers = account.get("followers", attrs.get("followers", 0))
    location = attrs.get("location", "")
    sector = screen.sector
    contradictions = []

    # --- Company snapshot ---
    snap = Section("Company snapshot")
    lead = repo.get("full_name") or fs.name
    snap.claims.append(Claim(
        f"{fs.name} — {sector} project ({lead}), {_fmt_int(repo_stars)} GitHub stars.",
        "observed", fs.profile_url))
    snap.claims.append(Claim(f"Sector (inferred): {sector}.", "inferred"))
    stage_claim = Claim(f"Stage (inferred): {attrs.get('inferred_stage', 'unknown')}.", "inferred")
    snap.claims.append(stage_claim)
    if location:
        snap.claims.append(Claim(f"Based in {location}.", "observed", fs.profile_url))
    else:
        snap.gaps.append("Location: not disclosed on public profile.")

    # --- Investment hypotheses (the 'why we'd invest' bullets) ---
    hyp = Section("Investment hypotheses")
    for c in fs.components:
        if c.value >= 65 and c.coverage >= 0.4:
            src = c.evidence[0] if c.evidence else ""
            hyp.claims.append(Claim(
                f"{c.name}: {c.value:.0f}/100 — a genuine strength.", "observed", src))
    if screen.market.stance == "bullish":
        hyp.claims.append(Claim(
            f"Market tailwind: {sector} is rated bullish ({screen.market.rating:.0f}/100).", "inferred"))
    if screen.idea_vs_market.stance in ("survives", "pivot-capable"):
        hyp.claims.append(Claim(
            f"Idea-vs-market: {screen.idea_vs_market.stance} — {screen.idea_vs_market.rationale}", "inferred"))
    if not hyp.claims:
        hyp.gaps.append("No component cleared the strength bar — thesis fit rests on potential, not proof.")

    # --- SWOT ---
    swot = Section("SWOT")
    strengths = [c for c in fs.components if c.value >= 65 and c.coverage >= 0.4]
    weaknesses = [c for c in fs.components if c.coverage >= 0.3 and c.value < 45]
    unknowns = [c for c in fs.components if c.coverage < 0.15]
    for c in strengths:
        swot.claims.append(Claim(f"Strength — {c.name} {c.value:.0f} ({c.evidence[0] if c.evidence else 'n/a'}).", "observed"))
    for c in weaknesses:
        swot.claims.append(Claim(f"Weakness — {c.name} only {c.value:.0f}/100.", "observed"))
    for c in unknowns:
        swot.gaps.append(f"Weakness/unknown — no signal on {c.name} (coverage {c.coverage:.0%}); verify.")
    if screen.market.stance == "bullish":
        swot.claims.append(Claim(f"Opportunity — bullish {sector} market: {screen.market.rationale}", "inferred"))
    risks = []
    if screen.market.stance == "bear":
        risks.append(f"Risk — {sector} market rated bear.")
    if screen.idea_vs_market.stance == "weak":
        risks.append("Risk — idea-vs-market is weak with thin founder signal.")
    if fs.confidence < 0.5:
        risks.append(f"Risk — founder assessment rests on limited evidence ({fs.confidence:.0%} confidence); wide band {fs.band[0]:.0f}-{fs.band[1]:.0f}.")
    if thesis_fit and any("off-thesis" in f for f in thesis_fit.flags):
        risks.append("Risk — off-thesis on geography/sector for the active fund.")
    for r in risks:
        swot.claims.append(Claim(r, "inferred"))

    # --- Problem & product ---
    pp = Section("Problem & product")
    desc = repo.get("description") or attrs.get("profile_text", "")[:200]
    if desc:
        pp.claims.append(Claim(f"Self-described: \"{desc.strip()[:200]}\".", "self-reported", repo.get("url", "")))
        pp.gaps.append("Problem framing is self-reported — not independently verified.")
    else:
        pp.gaps.append("Problem & product: not disclosed (no README/description/bio).")

    # --- Traction & KPIs ---
    tr = Section("Traction & KPIs")
    tr.claims.append(Claim(f"{_fmt_int(total_stars)} stars, {_fmt_int(total_forks)} forks across own projects.", "observed", fs.profile_url))
    if activity:
        tr.claims.append(Claim(
            f"{activity.get('recent_push_events_90d', 0)} public push events in the last ~90 days "
            f"({activity.get('active_repos_90d', 0)} active repos).", "observed", fs.profile_url))
    if followers:
        tr.claims.append(Claim(f"{_fmt_int(followers)} GitHub followers.", "observed", fs.profile_url))
    tr.gaps += [
        "Revenue / ARR: not disclosed.",
        "Users / DAU / retention: not disclosed.",
        "Unit economics (CAC, churn, sales cycle): not disclosed.",
        "Cap table & financials: not disclosed (pre-track-record).",
    ]

    # --- Contradiction check (light, honest) — linked to the specific claim ---
    if attrs.get("inferred_stage") == "growth/traction" and total_stars < 20:
        msg = "conflicts with low external engagement (<20 stars observed)"
        stage_claim.contradicts.append(msg)
        contradictions.append(f"Inferred stage 'growth/traction' {msg}.")

    # --- Data completeness: distinguish "we don't know" from "confirmed not present" ---
    completeness = {
        "location": "known" if location else "unknown",
        "traction": "known" if (total_stars or total_forks) else "unknown",
        "network/provenance": "known" if signals.get("orgs") else "unknown",  # GH orgs can be private → unknown
        "problem_statement": "known" if desc else "unknown",
        "test_discipline": ("confirmed-absent" if repo.get("has_tests") is False
                            else "known" if repo.get("has_tests") else "unknown"),
        "revenue/financials": "unknown",  # pre-track-record — not disclosed, not confirmed-absent
    }

    sections = [snap, hyp, swot, pp, tr]
    return Memo(fs.handle, fs.name, sections, contradictions, completeness)
