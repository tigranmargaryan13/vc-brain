# Front-end data contract

The UI binds to a single JSON produced by the intelligence pipeline. Generate it:

```bash
python -m sourcing.export [output.json] [--thesis thesis.json]
# default: data/frontend_data.json
# UI wiring: python -m sourcing.export web/public/founders.json
```

Pure local transform over the Memory store — no GitHub/LLM calls, safe to
regenerate anytime. Re-run `python -m sourcing.bridge --producthunt` (or
`analyze <handle>`) first to add/refresh founders, then re-export.

## Top-level shape

```jsonc
{
  "generated_at": "2026-07-19T…Z",
  "thesis":  { "name", "sectors":[], "geographies":[], "stages":[], "risk_appetite", "bar" },
  "summary": {
    "total_founders", "scoring_runs",
    "by_verdict": { "ADVANCE": n, "REVIEW": n, "PASS": n },   // funnel buckets
    "by_sector": { "ai infra": n, … },
    "trust_legend": { "High":…, "Med":…, "Low":…, "gap":… },
    "fairness": "…one-line safeguards statement for the UI to surface…"
  },
  "founders": [ FounderView, … ]   // sorted by thesis fit desc — this is the ranked funnel
}
```

## `FounderView` (one card)

```jsonc
{
  "handle", "name", "profile_url",
  "source_track": "outbound|inbound",     // funnel provenance
  "funnel_status": "screened",
  "founder_score": {
    "value": 64.7, "confidence": 0.81, "band": [58.1, 71.2],   // band = honest uncertainty range
    "components": [ { "name", "value", "coverage", "evidence":[] } ]   // Capability/Trajectory/Provenance/Traction
  },
  "capability": { "backend": "llm:gpt-4o|heuristic", "dimensions": {…} },
  "sector": "developer tools",
  "screen": {                              // THREE INDEPENDENT AXES — do not average
    "founder":        { "rating", "stance", "trend", "confidence", "rationale", "evidence":[] },
    "market":         { … "stance": "bullish|neutral|bear" … },
    "idea_vs_market": { … "stance": "survives|pivot-capable|market-carried|weak" … }
  },
  "reference_class": { "similarity", "best_archetype", "matched_features":[], "resembles_count", "caveat", "kind" },
  "thesis_fit": { "verdict": "ADVANCE|REVIEW|PASS", "fit_score", "quality_used", "matched":[], "flags":[], "rationale" },
  "memo": {
    "sections": [ { "title", "claims": [ Claim ], "gaps": [ "…not disclosed…" ] } ],
    "contradictions": [ "…" ],
    "data_completeness": { "location": "known|unknown|confirmed-absent", … }
  },
  "categories": { "verdict", "sector", "stage", "source_track", "founder_stance", "market_stance" },  // facet filters
  "tags": [ "review", "sector:developer tools", "cold-start", "off-thesis-geo", "has-data-gaps", … ]  // chip filters
}
```

### `Claim` (per-claim Trust — render as a badge)
```jsonc
{ "text", "status", "source", "trust": 0.9, "trust_label": "High|Med|Low",
  "verified": true|false|null, "contradicts": [ "…" ] }
```

## UI rendering hints
- **Funnel view**: iterate `founders` (already ranked); chip-filter on `tags` / facet-filter on `categories`; bucket by `summary.by_verdict`.
- **Founder card**: show the 3 `screen` axes side-by-side with trend arrows — **never blend into one number**.
- **Memo**: render each `Claim` with a Trust badge (`trust_label`) + a ✓/?/✗ from `verified`; show `gaps` as muted "not disclosed" rows; surface `data_completeness` and the `reference_class.caveat` verbatim.
- Always show `founder_score.band` (not just the point value) and `summary.fairness` — the honesty is the point.
