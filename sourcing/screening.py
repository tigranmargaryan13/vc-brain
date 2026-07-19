"""Multi-Axis Screening (brief MVP #6).

Every opportunity is scored along THREE independent axes — deliberately NOT
averaged, so the investor sees the disagreement instead of a blended number:

  * Founder        — who they are, traits, track record (our Founder Score).
  * Market         — sizing / competition, rated bullish | neutral | bear.
  * Idea vs Market — does the idea survive as-is, or is the team strong enough
                     to pivot?

Each axis also carries a TREND (improving | declining | stable | new) computed
against the previous screen in Memory, and each screen is written back to Memory
so the trend sharpens over time.

Market and Idea-vs-Market are heuristic-first (transparent, runnable keyless)
with an optional LLM deepening of the market rationale — the "thin-but-
transparent Intelligence layer" the brief prescribes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import memory
from . import thesis as thesis_mod

# Coarse, transparent market view keyed by sector. This is a placeholder for
# real market data / an LLM read — clearly labelled as such in the output.
MARKET_VIEW = {
    "ai infra": (80, "bullish", "Large and fast-growing; heavy demand for training/inference infra."),
    "ai": (76, "bullish", "Broad AI demand; crowded, so wedge and defensibility matter."),
    "developer tools": (68, "bullish", "Durable demand; monetization and bottoms-up GTM are the risk."),
    "data": (66, "bullish", "Steady enterprise demand; competitive incumbent landscape."),
    "security": (70, "bullish", "Structural tailwind; long enterprise sales cycles."),
    "fintech": (58, "neutral", "Large but heavily regulated and competitive."),
    "systems": (56, "neutral", "Foundational but long cycles / OSS-monetization risk."),
    "web3": (44, "bear", "Volatile and sentiment-driven; unclear durable demand."),
}
_DEFAULT_MARKET = (50, "neutral", "Insufficient signal to size the market — treated as neutral.")


@dataclass
class Axis:
    name: str
    rating: float          # 0-100
    stance: str            # Founder: strong/mixed/weak · Market: bullish/neutral/bear · Idea: survives/pivot-capable/weak
    trend: str             # improving | declining | stable | new
    confidence: float      # 0-1
    rationale: str
    evidence: list = field(default_factory=list)


@dataclass
class Screen:
    handle: str
    name: str
    sector: str
    founder: Axis
    market: Axis
    idea_vs_market: Axis   # three axes, intentionally NOT averaged into one number


def _classify_sector(attrs):
    tokens = thesis_mod._tokens(attrs.get("profile_text", ""))
    langs = [l.lower() for l in attrs.get("languages", [])]
    best, best_hits = None, 0
    for sector in MARKET_VIEW:
        hits = sum(
            1 for kw in thesis_mod._sector_keywords(sector)
            if (kw in tokens or kw in langs or (" " in kw and kw in " ".join(tokens)))
        )
        if hits > best_hits:
            best, best_hits = sector, hits
    return best


def _founder_axis(fs):
    r = fs.score
    stance = "strong" if r >= 68 else "mixed" if r >= 50 else "weak"
    ev = [f"{c.name} {c.value:.0f} (coverage {c.coverage:.0%})"
          for c in fs.components if c.coverage > 0]
    rationale = (
        f"Founder Score {r:.0f} (band {fs.band[0]:.0f}-{fs.band[1]:.0f}, "
        f"{fs.confidence:.0%} confidence), coverage-weighted across capability, "
        f"trajectory, provenance, and traction."
    )
    return Axis("Founder", r, stance, "new", fs.confidence, rationale, ev)


def _market_axis(sector, attrs):
    rating, stance, view = MARKET_VIEW.get(sector, _DEFAULT_MARKET)
    if sector is None:
        conf = 0.25
        rationale = "Market not identifiable from public signals — verify the sector directly."
        ev = []
    else:
        conf = 0.5   # coarse sector-level view, honest about being approximate
        rationale = f"Sector inferred as '{sector}'. {view}"
        ev = [f"sector inferred from tech signals: {', '.join(attrs.get('languages', [])[:4]) or 'n/a'}"]
    return Axis("Market", rating, stance, "new", conf, rationale, ev)


def _idea_axis(founder, market):
    """The interaction axis: does the idea survive, or can a strong team pivot?"""
    base = 0.5 * founder.rating + 0.5 * market.rating
    # A strong founder de-risks a weak market — they can pivot toward a better one.
    if founder.rating > market.rating and founder.rating >= 68:
        base += min(15, (founder.rating - market.rating) * 0.3)
    rating = round(min(100, base), 1)

    strong_f = founder.rating >= 68
    good_m = market.stance == "bullish"
    if strong_f and good_m:
        stance, why = "survives", "Strong team into a bullish market — the idea can be pursued as-is."
    elif strong_f and not good_m:
        stance, why = "pivot-capable", "Market is not clearly attractive, but the team is strong enough to pivot."
    elif not strong_f and good_m:
        stance, why = "market-carried", "Attractive market, but execution risk — founder signal is thin."
    else:
        stance, why = "weak", "Neither the market nor the founder signal is compelling as-is."
    conf = round(min(founder.confidence, market.confidence) * 0.9, 3)
    return Axis("Idea vs. Market", rating, stance, "new", conf, why, [])


def _trend(current, previous_rating):
    if previous_rating is None:
        return "new"
    delta = current - previous_rating
    if delta >= 3:
        return "improving"
    if delta <= -3:
        return "declining"
    return "stable"


def _apply_trends(screen):
    prev = memory.previous_screen(screen.handle)
    prev_axes = prev.get("axes", {}) if prev else {}
    for axis in (screen.founder, screen.market, screen.idea_vs_market):
        prior = prev_axes.get(axis.name, {}).get("rating") if prev_axes else None
        axis.trend = _trend(axis.rating, prior)


def _to_record(screen):
    return {
        "entity": screen.handle,
        "name": screen.name,
        "sector": screen.sector,
        "axes": {
            a.name: {
                "rating": round(a.rating, 1), "stance": a.stance,
                "trend": a.trend, "confidence": a.confidence,
            }
            for a in (screen.founder, screen.market, screen.idea_vs_market)
        },
        "scored_at": memory._now(),
    }


def screen_founder(fs, attrs, persist=True):
    """Build the 3-axis Screen for a scored founder. Persists for trend tracking."""
    sector = _classify_sector(attrs)
    founder = _founder_axis(fs)
    market = _market_axis(sector, attrs)
    idea = _idea_axis(founder, market)
    screen = Screen(fs.handle, fs.name, sector or "unknown", founder, market, idea)
    _apply_trends(screen)
    if persist:
        memory.append_screen(_to_record(screen))
    return screen
