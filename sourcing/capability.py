"""Capability assessment — the cold-start engine.

Reads a founder's actual code and rates demonstrated engineering maturity,
NOT popularity. Two backends:

  * LLM (preferred): the model reads the README + real source files and judges
    architecture, testing discipline, problem difficulty, and code quality.
    Used automatically when OPENAI_API_KEY is set and the `openai` SDK is
    installed.
  * Heuristic (fallback): a transparent rubric over structural signals
    (tests present, CI, docs, code volume, language spread). Always available,
    zero dependencies. Clearly labelled as a fallback so it's never mistaken
    for the real read.

Either way the output is the same shape: a 0-100 score, sub-dimensions, and a
rationale — so the rest of the pipeline doesn't care which backend ran.
"""
from __future__ import annotations

from . import llm

_CAP_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "dimensions": {
            "type": "object",
            "properties": {
                "architecture": {"type": "integer"},
                "testing": {"type": "integer"},
                "problem_difficulty": {"type": "integer"},
                "code_quality": {"type": "integer"},
            },
            "required": ["architecture", "testing", "problem_difficulty", "code_quality"],
            "additionalProperties": False,
        },
        "rationale": {"type": "string"},
    },
    "required": ["score", "dimensions", "rationale"],
    "additionalProperties": False,
}


def _build_prompt(repo):
    langs = ", ".join(repo.languages.keys()) or "unknown"
    readme = repo.readme[:3000]
    files = []
    for f in repo.source_files:
        files.append(f"--- {f['path']} ---\n{f['content'][:2000]}")
    files_blob = "\n\n".join(files) if files else "(no source files could be read)"
    return f"""You are assessing the engineering maturity of a founder candidate for a \
pre-track-record ("cold start") venture sourcing system. Judge DEMONSTRATED CAPABILITY \
from the code and structure itself — architecture, abstractions, testing discipline, and \
how hard the problem is. Explicitly ignore stars, forks, and popularity; a small, clean, \
ambitious project should score higher than a large derivative one.

Repository: {repo.full_name}
Description: {repo.description or "(none)"}
Languages: {langs}
Structure signals: tests={repo.has_tests}, CI={repo.has_ci}, docs={repo.has_docs}, size={repo.size_kb} KB

README (truncated):
{readme or "(no README)"}

Source samples (truncated):
{files_blob}

Score 0-100 on each dimension and overall (0 = no signal of capability, 100 = \
exceptional). Be calibrated and skeptical: most real early projects land 40-70. \
Give a two-sentence rationale citing what you actually saw in the code."""


def _assess_llm(repo):
    data = llm.complete_json(_build_prompt(repo), _CAP_SCHEMA, "capability_assessment")
    data["backend"] = f"llm:{llm.MODEL}"
    return data


def _assess_heuristic(repo):
    """Transparent structural rubric. Clearly a fallback, not the real read."""
    dims = {}
    # Testing discipline.
    dims["testing"] = 70 if repo.has_tests else 20
    if repo.has_ci:
        dims["testing"] = min(100, dims["testing"] + 15)
    # Architecture proxy: docs + code volume + multi-file structure.
    arch = 30
    if repo.has_docs:
        arch += 15
    if repo.size_kb > 500:
        arch += 15
    if len(repo.source_files) >= 2:
        arch += 10
    dims["architecture"] = min(100, arch)
    # Problem difficulty proxy: language spread + systems-language presence.
    systems = {"Rust", "C", "C++", "Go", "Zig", "CUDA"}
    diff = 35 + min(30, 8 * len(repo.languages))
    if systems & set(repo.languages.keys()):
        diff += 15
    dims["problem_difficulty"] = min(100, diff)
    # Code quality proxy: README substance + tests.
    cq = 30
    if len(repo.readme) > 400:
        cq += 20
    if repo.has_tests:
        cq += 15
    dims["code_quality"] = min(100, cq)

    score = round(sum(dims.values()) / len(dims))
    rationale = (
        "Heuristic fallback (no LLM key set): scored from structure only — "
        f"tests={repo.has_tests}, CI={repo.has_ci}, docs={repo.has_docs}, "
        f"{len(repo.languages)} language(s), {repo.size_kb} KB. "
        "Set OPENAI_API_KEY + install `openai` to read the code itself."
    )
    return {"score": score, "dimensions": dims, "rationale": rationale, "backend": "heuristic"}


def assess(repo):
    """Return {score, dimensions, rationale, backend} for one RepoDetail."""
    if repo is None:
        return {
            "score": 0,
            "dimensions": {},
            "rationale": "No non-fork repository with code was found.",
            "backend": "none",
        }
    if llm.available():
        try:
            return _assess_llm(repo)
        except Exception as e:  # any API/parse failure -> transparent fallback
            out = _assess_heuristic(repo)
            out["rationale"] += f" (LLM read failed: {type(e).__name__})"
            return out
    return _assess_heuristic(repo)
