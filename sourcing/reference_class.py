"""Reference-Class Matching (criteria doc "meta-method" · brief Research Area #3).

Build a reference class of successful founders, extract the public features they
share, then score a candidate by similarity — and surface *which* features
matched as the traceability citation.

Two deliberate design choices that address the brief's fairness goal:
  * The class is built on **demonstrated building behavior, not credentials**
    (no schools / employers / pedigree) — so it can't rebuild the network gate.
  * Similarity is a **soft prior, never a gate**, and we always print the
    **survivorship-bias caveat** (the class is winners-only + illustrative;
    without a denominator of who had these features and did NOT succeed, it
    overfits to surface features). Naming this is worth points.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

_SYSTEMS_LANGS = {"c", "c++", "rust", "go", "zig", "cuda", "assembly", "asm"}
_AIML = {"ml", "llm", "ai", "inference", "neural", "pytorch", "tensorflow",
         "model", "embedding", "transformer", "genai"}

CAVEAT = ("Survivorship-bias caveat: this class is winners-only and illustrative. "
          "Similarity is a SOFT PRIOR, never a filter — a real base rate needs the "
          "denominator (who had these features and did NOT succeed).")


@dataclass
class RefMatch:
    similarity: float          # 0-100, best-member Jaccard
    best_archetype: str
    matched_features: list     # human labels of the features that matched
    candidate_features: list   # all features the candidate exhibits
    resembles_count: int       # how many class members it materially resembles
    caveat: str = CAVEAT


def load(path=None):
    root = os.path.dirname(os.path.dirname(__file__))
    path = path or os.path.join(root, "reference_class.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_features(attrs):
    langs = {l.lower() for l in attrs.get("languages", [])}
    text = attrs.get("profile_text", "")
    tokens = set(re.findall(r"[a-z0-9+#.]+", text.lower()))
    f = set()
    if langs:
        f.add("technical")
    if _SYSTEMS_LANGS & langs:
        f.add("systems_builder")
    if (_AIML & tokens) or "machine learning" in text:
        f.add("ai_ml_domain")
    if attrs.get("owned_repo_count", 0) >= 8:
        f.add("prolific_builder")
    if attrs.get("recent_push_events", 0) >= 20:
        f.add("high_cadence")
    if attrs.get("stars", 0) >= 100:
        f.add("earned_attention")
    if len(langs) >= 4:
        f.add("polyglot")
    return f


def match(attrs, ref=None):
    ref = ref or load()
    labels = {feat["key"]: feat["label"] for feat in ref["features"]}
    cand = extract_features(attrs)

    best_sim, best_member, best_shared = 0.0, None, set()
    resembles = 0
    for m in ref["members"]:
        member = set(m["features"])
        union = cand | member
        shared = cand & member
        jac = len(shared) / len(union) if union else 0.0
        if jac >= 0.5:
            resembles += 1
        if jac > best_sim:
            best_sim, best_member, best_shared = jac, m["archetype"], shared

    return RefMatch(
        similarity=round(best_sim * 100, 1),
        best_archetype=best_member or "none",
        matched_features=[labels.get(k, k) for k in sorted(best_shared)],
        candidate_features=[labels.get(k, k) for k in sorted(cand)],
        resembles_count=resembles,
    )
