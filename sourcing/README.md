# sourcing — cold-start Founder Score

Turns a public footprint into a coverage-weighted, evidence-cited Founder Score
with an honest confidence band. Implements the capability engine + scoring core
from [../docs/sourcing-architecture.md](../docs/sourcing-architecture.md).

## Run

```bash
python -m sourcing.score <github_handle>
# e.g.
python -m sourcing.score torvalds
```

Runs with **no dependencies and no auth**. Two optional upgrades:

| Env var | Effect | Without it |
|---|---|---|
| `GITHUB_TOKEN` | Raises GitHub rate limit 60→5000/hr | Works, but ~6 API calls/run against the 60/hr cap |
| `OPENAI_API_KEY` (+ `pip install openai`) | The model **reads the actual code** to score capability | Transparent structural heuristic, clearly labelled |

## What it does

1. **Collect** ([github_collector.py](github_collector.py)) — one pluggable collector: handle → repos, the most substantial non-fork repo (picked by *code volume + recency*, **not stars**), file tree, README, source samples, recent push velocity, org memberships.
2. **Assess capability** ([capability.py](capability.py)) — LLM reads architecture/testing/difficulty/quality from the code itself; heuristic fallback otherwise. Same output shape either way.
3. **Score** ([founder_score.py](founder_score.py)) — four components (Capability, Trajectory, Provenance, Traction), each `value 0-100 × coverage 0-1`. Score = coverage-weighted mean; confidence from total coverage + cross-component corroboration.
4. **Persist** ([memory.py](memory.py)) — every run appends its raw signals and the scored result to `data/*.jsonl`, append-only (the "Memory" pillar — nothing discarded). Re-scoring a founder adds a new row, so the store carries trend over time.

## Memory / collected data

```bash
python -m sourcing.store            # funnel: latest score per founder, ranked
python -m sourcing.store <handle>   # score history (trend over time) for one founder
```

Data lives in `data/signals.jsonl` (raw normalized signals) and
`data/founder_scores.jsonl` (one row per scoring run). Both are plain JSONL —
`cat` them, or query with `jq`.

## Decision packet — the full analysis (`analyze`)

```bash
python -m sourcing.analyze <handle> [thesis.json]     # collect → screen → thesis → memo
python -m sourcing.analyze <handle> --from-memory     # rebuild from Memory, no GitHub calls
```

Produces the thing an investor acts on:

- **Multi-Axis Screen** ([screening.py](screening.py)) — three independent axes, **not averaged**: **Founder** (our score), **Market** (bullish/neutral/bear), **Idea-vs-Market** (survives / pivot-capable / market-carried / weak). Each carries a **trend** (improving/declining/stable/new) computed against the previous screen in Memory (`data/screens.jsonl`).
- **Reference-Class Prior** ([reference_class.py](reference_class.py) + [../reference_class.json](../reference_class.json)) — similarity to a curated class of winner archetypes, citing *which features matched* (brief Research Area #3). Built on **demonstrated building, not credentials** (anti-bias by design); surfaced as a **soft prior, never a gate**, always with the survivorship-bias caveat.
- **Thesis fit** — the fund verdict (ADVANCE/REVIEW/PASS).
- **Evidence-Backed Investment Memo** ([memo.py](memo.py)) — the 5 required sections (Company snapshot, Investment hypotheses, SWOT, Problem & product, Traction & KPIs). Each claim is a full **Claim object** — Trust Score (High/Med/Low) + `verified` (✓ observed / ? unchecked / ✗ conflicts) + `contradicts` links — and missing data is **flagged as a gap, never fabricated**. A **data-completeness** map distinguishes `known` / `unknown` / `confirmed-absent`, and a **fairness-safeguards** line states the bias handling out loud.

## Thesis Engine (the fund lens)

Configurable per fund (never hardcoded — brief FAQ #15). Edit
[../thesis.example.json](../thesis.example.json): sectors, geographies, stages,
check size, ownership target, risk appetite.

```bash
python -m sourcing.screen <handle> [thesis.json]   # score ONE founder + thesis recommendation
python -m sourcing.store --thesis [thesis.json]    # rank the whole funnel through the lens
```

Every candidate is **filtered and scored through the lens** ([thesis.py](thesis.py)):
sector overlap (soft boost), geography (explicit mismatch fails; unknown is
flagged, not penalized), stage (soft), and founder quality **read through the
risk appetite**:

- `conservative` → judges the confidence band's **lower** bound (uncertainty counts against)
- `balanced` → the point estimate
- `aggressive` → the **upper** bound (bets on a thin-data cold-start founder)

So the *same* founder can be a PASS for one fund and an ADVANCE for another —
that's the pillar. Verdicts: `ADVANCE` / `REVIEW` / `PASS`.

## The core mechanic: absence widens the band, never subtracts

```
score      = Σ(valueᵢ · coverageᵢ) / Σ(coverageᵢ)
confidence = f(total coverage, corroboration)
```

A founder with a brilliant repo and no network/funding/press gets a **high
Capability score with a WIDE confidence band** — surfaced for review, honestly
flagged as uncertain — instead of being zeroed out. That is the cold-start case
the challenge rewards, and the concrete stab at prediction intervals around soft
signals (Area of Research #1).

## Next collectors to add (same `value × coverage` contract)

- HN comment-quality miner → feeds Capability
- Stealth/quitting detector → a new "Intent" component
- Diaspora tracker / peer referrals → fills Provenance (currently degrades to 0 from GitHub alone)
