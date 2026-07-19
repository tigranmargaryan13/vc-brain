"""Ceiling / ambition assessment — the "potential" engine.

Where `capability.py` judges *how well* a founder builds, this judges *how big
and how original* what they're pointed at is — the power-law question the brief
frames as "the next 3 unicorns". It reads the founder's own words (bio, README,
project descriptions) and rates three dimensions:

  * problem_ambition — are they attacking something big and hard?
  * originality       — novel approach vs. a derivative clone?
  * domain_tailwind   — working in a fast-growing space?

Same two-backend contract as capability.py — LLM (gpt-4o) when a key is set,
transparent keyword heuristic otherwise — so the output shape is identical and
the rest of the pipeline doesn't care which ran. This is a *ceiling* read, so
scores skew optimistic-but-calibrated: it measures upside, not delivery.
"""
from __future__ import annotations

from . import llm

_AMB_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "dimensions": {
            "type": "object",
            "properties": {
                "problem_ambition": {"type": "integer"},
                "originality": {"type": "integer"},
                "domain_tailwind": {"type": "integer"},
            },
            "required": ["problem_ambition", "originality", "domain_tailwind"],
            "additionalProperties": False,
        },
        "rationale": {"type": "string"},
    },
    "required": ["score", "dimensions", "rationale"],
    "additionalProperties": False,
}


def build_text(profile):
    """The founder's own words — what we judge ambition from. Kept small and public."""
    parts = [profile.bio]
    if profile.top_repo:
        parts.append(profile.top_repo.description)
        parts.append(profile.top_repo.readme[:1500])
    for r in profile.owned_repos[:10]:
        if r.get("description"):
            parts.append(r["description"])
        parts.extend(r.get("topics") or [])
    return " ".join(p for p in parts if p).strip()


def _build_prompt(text):
    return f"""You are assessing the CEILING (ambition and upside potential) of a founder \
candidate for a power-law venture fund looking for the next generational company. \
You are NOT judging execution quality or traction — only how big and how original \
the thing they are pointed at is. A small, unfinished, wildly ambitious project \
should score HIGHER than a polished but derivative one.

Judge three dimensions from the founder's own words below:
- problem_ambition: are they attacking something big and structurally hard?
- originality: novel approach / contrarian insight vs. a clone of an existing product?
- domain_tailwind: are they in a fast-growing space with a real "why now"?

Founder's public text (bio, README, project descriptions):
{text[:3500]}

Score 0-100 on each dimension and overall (0 = no signal of ambition, 100 = \
generational upside). Reward boldness but stay calibrated: vague hype without a \
hard problem is not ambition. Give a two-sentence rationale citing what you saw."""


def _assess_llm(text):
    data = llm.complete_json(_build_prompt(text), _AMB_SCHEMA, "ambition_assessment")
    data["backend"] = f"llm:{llm.MODEL}"
    return data


# Transparent keyword rubric for the keyless fallback. Deliberately coarse and
# labelled as such — presence of hard-problem / original / tailwind language.
_HARD_PROBLEM = (
    "compiler", "kernel", "operating system", "database", "distributed", "protocol",
    "cryptography", "consensus", "real-time", "infrastructure", "from scratch",
    "low-level", "systems", "scale", "billion", "research", "novel algorithm",
    "simulation", "robotics", "autonomy", "foundation model", "reasoning",
)
_ORIGINAL = (
    "novel", "new approach", "rethink", "reimagine", "first", "unlike anything",
    "contrarian", "from first principles", "no one else", "reinvent", "unprecedented",
)
_TAILWIND = (
    "ai", "llm", "agent", "inference", "ml", "machine learning", "security",
    "climate", "energy", "bio", "genomics", "robotics", "quantum", "defense",
    "fintech", "developer tools", "data infrastructure",
)


def _hits(text, phrases):
    return sorted({p for p in phrases if p in text})


def _assess_heuristic(text):
    low = text.lower()
    hp, orig, tw = _hits(low, _HARD_PROBLEM), _hits(low, _ORIGINAL), _hits(low, _TAILWIND)
    dims = {
        "problem_ambition": min(100, 35 + 12 * len(hp)),
        "originality": min(100, 30 + 15 * len(orig)),
        "domain_tailwind": min(100, 40 + 12 * len(tw)),
    }
    score = round(sum(dims.values()) / len(dims))
    matched = ", ".join(hp + orig + tw) or "none"
    rationale = (
        "Heuristic fallback (no LLM key set): ambition scored from language cues only "
        f"(matched: {matched}). Set OPENAI_API_KEY + install `openai` to judge the text itself."
    )
    return {"score": score, "dimensions": dims, "rationale": rationale, "backend": "heuristic"}


def assess(profile):
    """Return {score, dimensions, rationale, backend} for a founder's ambition ceiling."""
    text = build_text(profile)
    if not text:
        return {
            "score": 0,
            "dimensions": {},
            "rationale": "No public text (bio/README/descriptions) to judge ambition from.",
            "backend": "none",
        }
    if llm.available():
        try:
            return _assess_llm(text)
        except Exception as e:  # any API/parse failure -> transparent fallback
            out = _assess_heuristic(text)
            out["rationale"] += f" (LLM read failed: {type(e).__name__})"
            return out
    return _assess_heuristic(text)
