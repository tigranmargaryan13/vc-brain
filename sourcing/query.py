"""Multi-Attribute Reasoning — one-pass natural-language compound query.

Brief MVP #3 / FAQ Q12: an investor types a *sentence* — e.g.

    "technical founder, Berlin, AI infra, no prior VC backing"

— and gets back the matching founders in a single pass. This module is the thin
shim that closes that gap: it turns the sentence into the SAME structured filters
the Thesis Engine already consumes, then reuses `thesis.evaluate` for the actual
matching. No second scorer, no new matching logic — sentence → Thesis → rank.

Two parse paths, same output:
  * `llm.available()`  → the model extracts the fields (the real path).
  * otherwise          → a keyless heuristic parser, so this runs with no API key
                         (same fallback contract as every other reasoning step).

Honesty first (project ethos): a stated attribute we don't actually track — e.g.
"no prior VC backing", since we hold no funding data — is surfaced as
*unverifiable*, never silently passed or used to reject. Geography off-mandate is
the only hard exclusion (it's a fund mandate, not a quality judgement); unknown
attributes are flagged, never penalised.

    python -m sourcing.query "technical founder, Berlin, AI infra, no prior VC backing"
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field

from . import identity
from . import llm
from . import memory
from . import thesis as thesis_mod

# --- vocab (heuristic path) -------------------------------------------------

# Sector aliases → canonical thesis sector. Ordered so a more specific phrase
# ("ai infra") is preferred over a broader one ("ai") when both would hit.
_SECTOR_ALIASES = [
    ("ai infra", ["ai infra", "ai infrastructure", "ml infra", "llm infra",
                  "inference infra", "gpu infra", "model serving"]),
    ("developer tools", ["developer tools", "devtools", "dev tools",
                         "developer-tools", "developer tooling"]),
    ("fintech", ["fintech", "payments", "banking", "financial services"]),
    ("security", ["security", "cybersecurity", "infosec", "appsec"]),
    ("data", ["data infrastructure", "data pipeline", "data platform",
              "analytics", "etl"]),
    ("web3", ["web3", "crypto", "blockchain", "defi"]),
    ("systems", ["systems programming", "low-level", "systems software",
                 "infrastructure"]),
    ("ai", ["ai", "artificial intelligence", "machine learning", "ml",
            "llm", "genai", "deep learning"]),
]

_GEO_TERMS = [
    "europe", "london", "berlin", "amsterdam", "paris", "remote",
    "san francisco", "bay area", "sf", "new york", "nyc", "boston",
    "seattle", "austin", "united states", "usa", "us", "uk",
    "germany", "france", "netherlands", "spain", "india", "canada",
    "tel aviv", "israel", "singapore", "toronto", "lisbon",
]

_STAGE_TERMS = {
    "pre-seed": ["pre-seed", "preseed", "pre seed"],
    "seed": ["seed"],
    "series a": ["series a", "series-a"],
    "growth": ["growth", "scale-up", "scaleup"],
    "idea": ["idea stage", "idea-stage"],
}

_RISK_TERMS = {
    "conservative": ["conservative", "risk-averse", "risk averse", "low risk", "cautious"],
    "aggressive": ["aggressive", "high risk", "high-risk", "risk-on", "risk on",
                   "willing to bet", "contrarian"],
    "balanced": ["balanced", "moderate"],
}

_TECHNICAL = ["technical founder", "technical co-founder", "technical", "engineer",
              "hacker", "deeply technical", "hands-on", "ships code", "builds"]
_COLD_START = ["cold start", "cold-start", "pre-launch", "prelaunch",
               "before fundraising", "before they raise", "no company yet",
               "idea stage", "not yet raised", "pre-company"]
_NO_FUNDING = ["no prior vc", "no vc backing", "no vc", "unfunded",
               "no funding", "bootstrapped", "never raised", "not funded",
               "no prior funding", "first-time raising"]


@dataclass
class QuerySpec:
    """The compound query, resolved into Thesis-compatible filters + facets."""
    raw: str
    source: str = "heuristic"          # "llm" | "heuristic" — how it was parsed
    sectors: list = field(default_factory=list)
    geographies: list = field(default_factory=list)
    stages: list = field(default_factory=list)
    risk_appetite: str = "balanced"
    min_score: float | None = None
    technical: bool | None = None
    cold_start: bool | None = None
    source_track: str | None = None    # "inbound" | "outbound"
    keywords: list = field(default_factory=list)
    unverifiable: list = field(default_factory=list)  # recognised, but not in our data


@dataclass
class QueryMatch:
    handle: str
    name: str
    fit: thesis_mod.ThesisFit
    passed: bool            # meets every HARD constraint (geo mandate + explicit facets)
    matched: list           # query attributes this founder satisfies
    unmet: list             # stated attributes not met (mostly soft / unknown)
    unverifiable: list      # facets we can't check for this founder
    rank: float             # sort key (thesis fit score)


# --- parsing ----------------------------------------------------------------

_PARSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sectors": {"type": "array", "items": {"type": "string"}},
        "geographies": {"type": "array", "items": {"type": "string"}},
        "stages": {"type": "array", "items": {"type": "string"}},
        "risk_appetite": {"type": "string",
                          "enum": ["conservative", "balanced", "aggressive"]},
        "technical": {"type": ["boolean", "null"]},
        "cold_start": {"type": ["boolean", "null"]},
        "source_track": {"type": ["string", "null"]},
        "min_score": {"type": ["number", "null"]},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "unverifiable": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sectors", "geographies", "stages", "risk_appetite", "technical",
                 "cold_start", "source_track", "min_score", "keywords", "unverifiable"],
}

_PARSE_PROMPT = """You turn a VC's natural-language founder-search sentence into structured filters, in ONE pass.

Query: {query}

Extract:
- sectors: canonical tech sectors mentioned. Prefer these when they fit: {sectors}.
- geographies: cities/regions/countries mentioned (as written).
- stages: funding/company stages mentioned (e.g. pre-seed, seed, series a, growth, idea).
- risk_appetite: conservative | balanced | aggressive. Default "balanced" if unstated.
- technical: true if a technical/engineer/hands-on-builder founder is required, else null.
- cold_start: true if they want pre-launch / pre-fundraising / very-early founders, else null.
- source_track: "inbound" if they specifically want founders who applied, "outbound" if founders we proactively found, else null.
- min_score: a 0-100 quality floor ONLY if a bar is implied (e.g. "top", "exceptional"), else null.
- keywords: other distinctive descriptive terms worth matching against a profile (e.g. "open source", "ex-faanng"). Lowercase.
- unverifiable: attributes we CANNOT check because we hold no such data — funding history, revenue, cap table, prior VC backing, headcount. List them verbatim (e.g. "no prior VC backing"). Do NOT invent filters for these.

Return only the JSON object."""


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _has(term, low):
    """Whole-word-ish containment: word boundaries around alphanumerics."""
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low) is not None


def _heuristic_parse(text):
    low = _norm(text)
    spec = QuerySpec(raw=text, source="heuristic")

    for canonical, aliases in _SECTOR_ALIASES:
        if any(_has(a, low) for a in aliases) and canonical not in spec.sectors:
            spec.sectors.append(canonical)
    # keep "ai infra" from being shadowed by a lone "ai" hit, and vice-versa
    if "ai infra" in spec.sectors and "ai" in spec.sectors:
        spec.sectors.remove("ai")

    spec.geographies = [g for g in _GEO_TERMS if _has(g, low)]
    # drop the broad "us"/"europe" when a more specific place in it was also named
    if any(c in spec.geographies for c in ("san francisco", "new york", "boston",
                                           "seattle", "austin")):
        spec.geographies = [g for g in spec.geographies if g not in ("us", "usa", "united states")]

    for canonical, aliases in _STAGE_TERMS.items():
        if any(_has(a, low) for a in aliases):
            spec.stages.append(canonical)

    for risk, terms in _RISK_TERMS.items():
        if any(_has(t, low) for t in terms):
            spec.risk_appetite = risk
            break

    if any(_has(t, low) for t in _TECHNICAL):
        spec.technical = True
    if any(_has(t, low) for t in _COLD_START):
        spec.cold_start = True
    if _has("inbound", low) or _has("applied", low):
        spec.source_track = "inbound"
    elif _has("outbound", low):
        spec.source_track = "outbound"
    if any(_has(t, low) for t in ("top", "exceptional", "strongest", "best-in-class")):
        spec.min_score = 70.0
    if any(_has(t, low) for t in _NO_FUNDING):
        spec.unverifiable.append("no prior VC backing (we hold no funding data)")
    return spec


def _from_llm(data, text):
    spec = QuerySpec(raw=text, source="llm")
    spec.sectors = [s.lower() for s in (data.get("sectors") or [])]
    spec.geographies = [g for g in (data.get("geographies") or [])]
    spec.stages = [s.lower() for s in (data.get("stages") or [])]
    spec.risk_appetite = (data.get("risk_appetite") or "balanced").lower()
    spec.technical = data.get("technical")
    spec.cold_start = data.get("cold_start")
    st = data.get("source_track")
    spec.source_track = st.lower() if isinstance(st, str) else None
    spec.min_score = data.get("min_score")
    spec.keywords = [k.lower() for k in (data.get("keywords") or [])]
    spec.unverifiable = list(data.get("unverifiable") or [])
    return spec


def parse_query(text):
    """Sentence → QuerySpec. LLM when available, heuristic otherwise."""
    if llm.available():
        try:
            prompt = _PARSE_PROMPT.format(
                query=text,
                sectors=", ".join(c for c, _ in _SECTOR_ALIASES),
            )
            data = llm.complete_json(prompt, _PARSE_SCHEMA, schema_name="founder_query")
            return _from_llm(data, text)
        except Exception:
            pass   # any model/transport failure → deterministic fallback
    return _heuristic_parse(text)


# --- matching (reuses thesis.evaluate) --------------------------------------

def to_thesis(spec):
    """Build the ad-hoc Thesis the query implies — fed straight to thesis.evaluate."""
    return thesis_mod.Thesis.from_dict({
        "name": f"Ad-hoc query: {spec.raw}",
        "sectors": spec.sectors,
        "geographies": spec.geographies,
        "stages": spec.stages,
        "risk_appetite": spec.risk_appetite,
        "min_score": spec.min_score,
    })


_COLD_STAGES = {"pre-seed/idea", "early traction"}


def match_founder(spec, thesis_obj, fs):
    """Run the founder through the query's thesis, then the extra facets."""
    fit = thesis_mod.evaluate(thesis_obj, fs)
    attrs = getattr(fs, "attributes", {}) or {}
    matched, unmet = [], []
    passed = True

    # Geography — the one HARD gate (fund mandate). Unknown is flagged, not failed.
    if spec.geographies:
        if any("geography off-thesis" in f for f in fit.flags):
            passed = False
            unmet.append(f"geography off-mandate: {attrs.get('location') or 'unknown'}")
        elif any(m.startswith("geography:") for m in fit.matched):
            matched.append(f"geography: {attrs.get('location') or 'in-mandate'}")
        else:
            unmet.append("geography unknown — unverified (not excluded)")

    # Sector / stage — soft, surfaced from the thesis result.
    if spec.sectors:
        hit = next((m for m in fit.matched if m.startswith("sector:")), None)
        (matched if hit else unmet).append(hit or "no sector overlap")

    # Technical — soft signal from demonstrated code + capability.
    if spec.technical:
        techy = bool(attrs.get("languages")) or fs.score >= 55
        if techy:
            langs = ", ".join(attrs.get("languages", [])[:3])
            matched.append("technical: demonstrated code" + (f" ({langs})" if langs else ""))
        else:
            unmet.append("technical signal weak — unverified")

    # Cold-start — HARD when asked (it's a known categorical fact).
    if spec.cold_start:
        stage = attrs.get("inferred_stage", "unknown")
        if stage in _COLD_STAGES:
            matched.append(f"cold-start: {stage}")
        else:
            passed = False
            unmet.append(f"not cold-start (stage: {stage})")

    # Source track — HARD when asked.
    if spec.source_track:
        st = attrs.get("source_track", "outbound")
        if st == spec.source_track:
            matched.append(f"track: {st}")
        else:
            passed = False
            unmet.append(f"track {st} ≠ requested {spec.source_track}")

    # Free keywords — soft profile match.
    ptext = attrs.get("profile_text", "")
    for kw in spec.keywords:
        if kw and kw in ptext:
            matched.append(f"keyword: {kw}")

    return QueryMatch(
        handle=fs.handle, name=fs.name, fit=fit, passed=passed,
        matched=matched, unmet=unmet, unverifiable=list(spec.unverifiable),
        rank=fit.fit_score,
    )


def load_people():
    """The scored, cross-source-deduped founders from Memory (same set as export)."""
    latest, _counts = memory.latest_by_entity()
    return identity.resolve_and_merge(latest)


def resolve(text, people=None):
    """Full one-pass resolve: sentence → filters → ranked matches over Memory."""
    people = load_people() if people is None else people
    spec = parse_query(text)
    thesis_obj = to_thesis(spec)
    matches = [match_founder(spec, thesis_obj, fs) for fs in people]
    # Passing founders first, then by thesis fit desc.
    matches.sort(key=lambda m: (m.passed, m.rank), reverse=True)
    return {"spec": spec, "matches": matches}


# --- serialization (for the API / CLI) --------------------------------------

def spec_to_dict(spec):
    return {
        "raw": spec.raw, "resolved_by": spec.source,
        "sectors": spec.sectors, "geographies": spec.geographies,
        "stages": spec.stages, "risk_appetite": spec.risk_appetite,
        "min_score": spec.min_score, "technical": spec.technical,
        "cold_start": spec.cold_start, "source_track": spec.source_track,
        "keywords": spec.keywords, "unverifiable": spec.unverifiable,
    }


def match_to_dict(m):
    return {
        "handle": m.handle, "name": m.name, "passed": m.passed,
        "fit_score": round(m.fit.fit_score, 1), "verdict": m.fit.verdict,
        "matched": m.matched, "unmet": m.unmet, "unverifiable": m.unverifiable,
        "thesis_rationale": m.fit.rationale,
    }


# --- CLI --------------------------------------------------------------------

def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print('usage: python -m sourcing.query "technical founder, Berlin, AI infra, no prior VC backing"',
              file=sys.stderr)
        return 2
    text = " ".join(argv)
    result = resolve(text)
    spec, matches = result["spec"], result["matches"]
    passed = [m for m in matches if m.passed]

    print(f"\n  QUERY: {text}")
    print(f"  parsed by: {spec.source}")
    print("  ── resolved to filters ──")
    print(f"    sectors={spec.sectors or '—'}  geo={spec.geographies or '—'}  "
          f"stages={spec.stages or '—'}  risk={spec.risk_appetite}")
    if spec.technical or spec.cold_start or spec.source_track or spec.keywords:
        print(f"    facets: technical={spec.technical} cold_start={spec.cold_start} "
              f"track={spec.source_track} keywords={spec.keywords or '—'}")
    if spec.unverifiable:
        print(f"    ⚠ unverifiable (no data to check): {'; '.join(spec.unverifiable)}")
    print(f"\n  {len(passed)}/{len(matches)} founders match all hard constraints\n")

    for m in passed[:15]:
        print(f"  ● {m.name} (@{m.handle})  fit {m.fit.fit_score:.0f}/100  [{m.fit.verdict}]")
        if m.matched:
            print(f"      ✓ {' · '.join(m.matched)}")
        if m.unmet:
            print(f"      ~ {' · '.join(m.unmet)}")
        if m.unverifiable:
            print(f"      ⚠ {' · '.join(m.unverifiable)}")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
