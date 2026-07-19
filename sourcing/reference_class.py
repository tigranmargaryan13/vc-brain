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

# Track-record & intent keyword signals (matched against public bio/repo text and,
# for inbound applicants, their one-liner/notes). These are DEMONSTRATED HISTORY or
# STATED INTENT — never employer/school pedigree. Soft priors, so light false
# positives are tolerable; the survivorship caveat is always printed.
_PRIOR_FOUNDER = ("founder", "co-founder", "cofounder", "founded ", "ex-founder",
                  "serial entrepreneur", "previously founded", "2x founder", "3x founder")
_PRIOR_EXIT = ("acquired by", "was acquired", "acquisition by", "exited", "ipo",
               "went public", "sold my", "sold the company", "sold to ")
_PRIOR_FAILED = ("failed startup", "shut down", "wound down", "shuttered",
                 "startup that didn't", "company didn't work", "previous startup that")
_RESEARCH = ("arxiv", "co-authored", "google scholar", "phd", "ph.d", "neurips",
             "icml", "iclr", "cvpr", "research scientist", "published a paper")
_MODEL_RELEASE = ("huggingface", "hugging face", "pretrained", "fine-tuned",
                  "open-sourced", "released a model", "model checkpoint", "model weights")
_DEPARTURE = ("stealth", "leaving to build", "left my job", "building something new",
              "in stealth", "open to work", "recently departed")

# Major startup hubs — presence OUTSIDE them is a POSITIVE underdog signal here
# (never a penalty; geography is a fund mandate, not a quality judgement).
_HUBS = ("san francisco", "sf bay", "bay area", "palo alto", "mountain view",
         "menlo park", "new york", "nyc", "brooklyn", "boston", "cambridge, ma",
         "seattle", "los angeles", "london", "berlin", "paris", "tel aviv",
         "beijing", "shanghai", "bangalore", "bengaluru", "singapore")

# Pedigree/employer features present in personas.seed.json that we DELIBERATELY do
# not detect — inferring them would rebuild the network/credential gate this project
# rejects (see module docstring). Listed so the omission is explicit, not an oversight.
PEDIGREE_EXCLUDED = ("founder_factory_alum", "early_operator", "frontier_lab")

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
    """Load the reference class. Defaults to the evidence-backed personas
    (personas.seed.json), falling back to the illustrative reference_class.json."""
    root = os.path.dirname(os.path.dirname(__file__))
    if path is None:
        for name in ("personas.seed.json", "reference_class.json"):
            cand = os.path.join(root, name)
            if os.path.exists(cand):
                path = cand
                break
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _text_has(text, needles):
    return any(n in text for n in needles)


def extract_features(attrs):
    """Map a candidate's public attributes to reference-class feature keys.

    Every feature here is DEMONSTRATED BUILDING, TRACK RECORD, or STATED INTENT —
    detectable from public signal without any school/employer/pedigree input. The
    three pedigree features in personas.seed.json (see PEDIGREE_EXCLUDED) are
    intentionally never produced, so matching can't rebuild the network gate.
    """
    langs = {l.lower() for l in attrs.get("languages", [])}
    app = attrs.get("application") or {}
    text = " ".join([
        attrs.get("profile_text", "") or "",
        str(app.get("one_liner", "")), str(app.get("notes", "")), str(app.get("company", "")),
    ]).lower()
    tokens = set(re.findall(r"[a-z0-9+#.]+", text))
    f = set()

    # ---- demonstrated building (source-agnostic) ----
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
    if attrs.get("stars", 0) >= 100 or attrs.get("native_upvotes_career", 0) >= 300:
        f.add("earned_attention")
    if len(langs) >= 4:
        f.add("polyglot")

    # ---- track record & intent (fair: history / intent, NOT pedigree) ----
    tenure_days = max(attrs.get("account_age_days", 0) or 0, attrs.get("native_tenure_days", 0) or 0)
    if tenure_days >= 3 * 365:
        f.add("domain_tenure")
    if _text_has(text, _PRIOR_FOUNDER):
        f.add("prior_founder")
    if _text_has(text, _PRIOR_EXIT):
        f.add("prior_exit")
    if _text_has(text, _PRIOR_FAILED):
        f.add("prior_failed")
    if _text_has(text, _RESEARCH):
        f.add("has_publications")
    if _text_has(text, _MODEL_RELEASE):
        f.add("model_release")
    stage = ((attrs.get("inferred_stage", "") or "") + " " + str(app.get("stage", ""))).lower()
    if attrs.get("source_track") == "inbound" and (
            _text_has(stage, ("idea", "stealth", "pre-seed")) or _text_has(text, _DEPARTURE)):
        f.add("departure_intent")

    # ---- THE ALPHA: high capability + low network coverage. Fires ON demonstrated
    # capability, never on demographics — the mispriced under-networked builder. ----
    strong_building = bool({"prolific_builder", "earned_attention", "high_cadence"} & f)
    low_provenance = (attrs.get("followers", 0) or 0) < 50
    if strong_building and low_provenance:
        f.add("high_cap_low_provenance")

    # ---- geography as a POSITIVE underdog signal (never a gate; on its own it can't
    # carry an archetype — the winner personas pair it with capability features). ----
    loc = (attrs.get("location", "") or "").lower()
    if loc and not _text_has(loc, _HUBS):
        f.add("non_hub_geo")

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
