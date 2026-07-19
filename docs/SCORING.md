# VC Brain — Scoring Reference

How VC Brain turns a founder's public footprint into a score. This is the
reference for the two scoring layers; the code lives in `sourcing/`.

> **One-sentence definition:** a coverage- and power-law-weighted evidence
> aggregator that rates a founder on **demonstrated capability over credentials**,
> treats **missing data as uncertainty rather than a penalty** (cold-start safe),
> and keeps **Founder / Market / Idea as three separate, trend-aware signals**
> instead of one collapsed number.

---

## Two layers

| Layer | Scope | Lives on | Code |
|---|---|---|---|
| **Founder Score** | per **person**, persists across startups | Founder entity (Memory) | `founder_score.py` |
| **Multi-Axis Screen** | per **opportunity** | Startup entity | `screening.py` |

The Founder Score is **one input** to the screen's Founder axis — not a substitute for it.

---

## Layer 1 — Founder Score (0–100 + confidence band)

Each component carries **two** numbers, never one:

- **value** (0–100) — how good the signal is
- **coverage** (0–1) — how much real data backs it

### The combine step (`_aggregate`)

```
score      = Σ(value · coverage · weight) / Σ(coverage · weight)
confidence = clamp(0.25 + 0.55·avg_coverage + 0.04·corroboration, 0.10, 0.95)
margin     = (1 − confidence) · 35
band       = (score − margin, score + margin)          # clamped to [0, 100]
```

- `avg_coverage` = mean coverage across all components
- `corroboration` = number of components with coverage > 0.15
- If total weighted coverage is 0 → `score 0, confidence 0.10, band (0, 100)` — i.e. *"we know nothing,"* not *"this founder is bad."*
- **Confidence depends only on data density** — `weight` never enters it.

### The seven components

| Component | value (0–100) | coverage (0–1) | weight | Backend |
|---|---|---|---|---|
| **Capability** | LLM/heuristic read of the *code itself* | `min(1, 0.35 + 0.4·vol + 0.25·files)` | **1.3** | `capability.py` (LLM) |
| **Skills** | `clamp(30 + 12·breadth)` (distinct languages shipped) | `min(1, breadth/4)` | 1.0 | keyless |
| **Trajectory** | `clamp(pushes·3 + activeRepos·8)` | `min(1, (pushes + ownedRepos)/6)` | 1.0 | keyless |
| **Ceiling** (potential) | LLM/heuristic ambition read | `min(1, 0.3 + textLen/2000)` | **1.5** | `ambition.py` (LLM) |
| **Intent** `[+only]` | `clamp(35·numTells)` | `min(1, numTells/2)` | 1.2 | keyless |
| **Provenance** | `clamp(numOrgs·25)` | `min(1, numOrgs/3)` | 0.8 | keyless |
| **Traction** | `clamp(stars·2 + forks·3)` | `min(1, (stars + forks)/10)` | 1.0 | keyless |

`vol = min(1, repo.size_kb/800)`, `files = min(1, sourceFiles/3)`.

### Weights = the power-law lens (`WEIGHTS`)

Not every criterion matters equally for a "next 3 unicorns" fund. Weight tunes a
component's **pull on the score**, never its confidence.

- **Up:** Ceiling `1.5`, Capability `1.3`, Intent `1.2` — potential, demonstrated skill, and the cold-start edge.
- **Down:** Provenance `0.8` — leaning on network signal rebuilds the network gate the project exists to break.

### What each component means

- **Capability** — *how well* they build. An LLM reads the README + real source files and rates architecture / testing / problem difficulty / code quality, explicitly ignoring stars and popularity. This is the anti-credential core.
- **Skills** — demonstrated technical breadth (languages actually shipped in code, not claimed). Commercial/domain skills are deferred to post-conversion (Tier 2), so their absence leaves coverage partial rather than penalizing.
- **Trajectory** — sustained recent building (push events + active repos).
- **Ceiling** — *how big and original* the thing is (problem ambition / originality / domain tailwind), judged from the founder's own words. Measures upside, not delivery.
- **Intent** `[+only]` — the cold-start edge: "becoming a founder" tells before the title exists (stealth/waitlist language, blank bio while actively shipping, prolific unmonetized building). Presence scores up; absence never down.
- **Provenance** — org / network membership. Deliberately near-zero coverage from GitHub alone; filled later by a diaspora/referral collector.
- **Traction** — external engagement (stars/forks). Near-zero coverage for unknowns, so absence doesn't drag the score.

---

## Layer 2 — Multi-Axis Screen (three independent axes, never averaged)

The screen scores an opportunity along three axes that are **kept separate**, so
an investor sees the *disagreement* instead of a blended number.

| Axis | What it rates | Stances | Confidence |
|---|---|---|---|
| **Founder** | the Founder Score above | strong ≥68 · mixed ≥50 · weak | inherited (`fs.confidence`) |
| **Market** | sector view (lookup / LLM) | bullish · neutral · bear | 0.5 (0.25 if sector unknown) |
| **Idea vs. Market** | does the idea survive **as-is**? | survives ≥65 · needs-validation ≥45 · weak | `min(0.7, 0.3 + textLen/1500)` |

- **Idea vs. Market is scored independently** on the idea's *own* evidence — its
  problem/product description — via `idea.py` (coherence / problem_evidence /
  defensibility). It is **not** derived from the Founder or Market ratings, so a
  strong founder with a weak idea shows real disagreement. No description →
  neutral `50 / needs-validation / low confidence` (absence ≠ penalty), never "weak".

### Trend

Each axis carries a trend vs. its previous score in Memory (`data/screens.jsonl`):
`improving` (Δ ≥ +3) · `declining` (Δ ≤ −3) · `stable` · `new` (no prior screen).

---

## Layer 3 — Outcome Prior (reference-class matching *with a denominator*)

`reference_class.py` scores **similarity** to winner archetypes — the class is
`personas.seed.json`, six evidence-backed founder personas (Domain Defector,
Comeback Operator, Prolific Builder, Deep-Tech Researcher, Under-Networked
Contrarian, …), each defined by public features. `extract_features` detects 16 of
them from demonstrated building, track record, and stated intent; three
pedigree/employer features in the seed (`founder_factory_alum`, `early_operator`,
`frontier_lab`, listed in `PEDIGREE_EXCLUDED`) are **deliberately never detected**,
so matching cannot rebuild the network/credential gate. Similarity is useful, but
it is not prediction, and comparing only to winners rebuilds the survivorship-bias
gate the project exists to break. `outcome_prior.py` adds the missing
**denominator** and turns it into a base-rate signal.

**Two cohorts, both feature-extracted the same way** (GitHub collector → attrs →
`reference_class.extract_features`), fit by `scripts/build_outcome_model.py`:
- **winners** — a curated set of proven founders (`data/outcome_cohort.json`)
- **comparison** — a baseline of typical active builders + real ProductHunt-sourced candidates (outcome *unlabeled* — the population a winner must be distinguished from)

**Per-feature likelihood ratio, combined with naive Bayes:**
```
LR(f)          = P(f | winner) / P(f | comparison)          # Laplace-smoothed; >1 predicts
posterior_odds = prior_odds · Π LR(f present) · Π LR̄(f absent)
P(resembles)   = posterior_odds / (1 + posterior_odds)
band           = P ± 1/√(min_support)                        # widens when the sample is thin
```

Output (`OutcomePrior`): a 0–100 score + band + confidence, the **base rate** for
context, and the **top ± feature drivers** with their lift — surfaced in the
decision packet (`analyze.py`) and the frontend contract (`export.py`).

**Why the denominator matters (real result on the seed cohorts):** against a
baseline of elite OSS developers, `technical` (1.05), `earned attention` (0.97),
`polyglot` (0.97) and even `prolific OSS` (0.90) collapse to **noise** — only
`high shipping cadence` (1.40) and `systems-building` (1.20) show real lift. A
similarity-to-winners model scores all of them as gold; the base-rate model shows
which actually separate proven founders from the crowd.

**Guarantees:** soft prior, never a gate · features are demonstrated-building only,
so lift can't encode a pedigree gate · every LR is visible (fairness audit — drop a
bias proxy and show the number that justified it) · label is *"resembles a proven
founder,"* not ground-truth success · **refit on real outcomes as Memory accrues
them** (the flywheel).

Rebuild the model: `python scripts/build_outcome_model.py` → `data/outcome_model.json`.

---

## Backends: LLM-optional, keyless-safe

`capability.py`, `ambition.py`, and `idea.py` share one contract (`llm.py`):

- **LLM (preferred):** OpenAI `gpt-4o` when `OPENAI_API_KEY` is set and the `openai` SDK is installed — reads the actual text/code.
- **Heuristic (fallback):** a transparent keyword/structure rubric, always available, zero dependencies, **clearly labelled** so it's never mistaken for the real read.

Output shape is identical either way, so the rest of the pipeline is backend-agnostic.

---

## Trust Score (memo, per claim)

Trust is **per claim**, not one number for the company (`memo.py`):

| Status | Trust | Meaning |
|---|---|---|
| observed | 0.90 | a primary source states it directly |
| inferred | 0.55 | derived by us (sector, stage) |
| self-reported | 0.40 | the founder's own words, unverified |
| contradiction | ≤0.30 | conflicts with other evidence (trust capped low) |

Missing data is flagged explicitly (`"Revenue: not disclosed"`) rather than guessed.

---

## Invariants (the design guarantees)

1. **Absence never subtracts.** A missing signal drops that component's *coverage* to 0, which **widens the band** — it is never scored as a zero. Cold-start safe.
2. **Weight moves the score, not the confidence.** Importance and certainty stay separate.
3. **The three axes are never collapsed** into one number. Disagreement is surfaced.
4. **Every component/claim cites its evidence.** Traceable, not a black box.
5. **`[bias]` signals stay weak and non-gating; `[+only]` signals never penalize absence.**

---

## Persistence (Memory)

Every run appends to append-only JSONL under `data/` — nothing discarded:

- `signals.jsonl` — raw collected signals (source-tagged, timestamped)
- `founder_scores.jsonl` — scored results (components, weights, band, backends)
- `screens.jsonl` — 3-axis screens (drives the trend)

A `FounderScore` can be rebuilt from a persisted record (`from_record`) without
re-hitting GitHub — this is what `analyze.py --from-memory` uses.

---

*See also: `docs/sourcing-architecture.md` (the pipeline), `docs/ARCHITECTURE.md`
(two-layer services/sourcing split), `../vc_brain_criteria_and_schema.md` (the
full criteria menu + data schema).*
