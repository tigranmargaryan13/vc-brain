"""Idea assessment — the Idea-vs-Market axis, scored on its OWN evidence.

This axis answers "does the idea survive scrutiny as-is?" and is deliberately
INDEPENDENT of the Founder and Market axes: it reads the idea's own description
(problem / product / README text) and judges the concept on its merits, so the
three axes can genuinely disagree instead of one being a blend of the others.

Three dimensions:
  * coherence        — is it a clear, specific concept, not vague hand-waving?
  * problem_evidence — is there a real, non-trivial problem being solved?
  * defensibility    — a wedge / something proprietary vs. easily commoditized?

Same two-backend contract as capability.py / ambition.py — LLM (gpt-4o) when a
key is set, transparent keyword heuristic otherwise. Distinct from Ceiling
(ambition): Ceiling asks how BIG the upside is; this asks whether the idea, as
stated, HOLDS TOGETHER.
"""
from __future__ import annotations

from . import llm

_IDEA_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "dimensions": {
            "type": "object",
            "properties": {
                "coherence": {"type": "integer"},
                "problem_evidence": {"type": "integer"},
                "defensibility": {"type": "integer"},
            },
            "required": ["coherence", "problem_evidence", "defensibility"],
            "additionalProperties": False,
        },
        "rationale": {"type": "string"},
    },
    "required": ["score", "dimensions", "rationale"],
    "additionalProperties": False,
}


def _build_prompt(text):
    return f"""You are assessing whether a startup IDEA survives scrutiny AS-IS, for a \
venture sourcing system. Judge the idea ON ITS OWN MERITS — do NOT reward the \
team's talent or the market's size (those are scored separately). A clear, \
specific idea that solves a real, hard problem with some defensibility should \
score high even if described plainly; vague, buzzword-heavy, or obviously \
commoditized ideas should score low even if ambitious.

Judge three dimensions from the idea's own description below:
- coherence: is it a specific, well-formed concept, or vague hand-waving?
- problem_evidence: is there a real, non-trivial problem being solved?
- defensibility: is there a wedge or something proprietary, vs. easily copied?

Idea / product description (bio, README, project text):
{text[:3000]}

Score 0-100 on each dimension and overall (0 = no coherent idea, 100 = a sharp, \
defensible idea that clearly survives as-is). Be skeptical of ideas that are only \
a restatement of a popular category. Give a two-sentence rationale citing the text."""


def _assess_llm(text):
    data = llm.complete_json(_build_prompt(text), _IDEA_SCHEMA, "idea_assessment")
    data["backend"] = f"llm:{llm.MODEL}"
    return data


# Transparent keyword rubric for the keyless fallback — coarse and labelled.
_PROBLEM = ("problem", "pain", "struggle", "instead of", "so that", "because", "frustrat",
            "hard to", "no easy way", "manually", "waste", "slow", "expensive")
_DEFENSE = ("proprietary", "novel", "unlike", "moat", "unique", "patent", "algorithm",
            "from scratch", "custom", "first to", "no one else", "our own")


def _hits(text, phrases):
    return sorted({p for p in phrases if p in text})


def _assess_heuristic(text):
    low = text.lower()
    prob, defe = _hits(low, _PROBLEM), _hits(low, _DEFENSE)
    length = len(low)
    dims = {
        # Coherence: a real description of some length reads as more coherent than a one-liner.
        "coherence": min(100, 25 + min(45, length // 20)),
        "problem_evidence": min(100, 30 + 12 * len(prob)),
        "defensibility": min(100, 30 + 14 * len(defe)),
    }
    score = round(sum(dims.values()) / len(dims))
    matched = ", ".join(prob + defe) or "none"
    rationale = (
        "Heuristic fallback (no LLM key set): idea scored from description length and "
        f"language cues only (matched: {matched}). Set OPENAI_API_KEY + install `openai` "
        "to judge whether the idea actually holds together."
    )
    return {"score": score, "dimensions": dims, "rationale": rationale, "backend": "heuristic"}


def assess(text):
    """Return {score, dimensions, rationale, backend} for an idea description string."""
    text = (text or "").strip()
    if not text:
        return {
            "score": 0,
            "dimensions": {},
            "rationale": "No idea/product description available to assess.",
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
