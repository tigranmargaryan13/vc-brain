# VC Brain

An AI-first VC operating system: **surface exceptional founders before they fundraise, score them on merit (not network), and produce a decision-ready investment memo — in minutes.** Built for the Maschmeyer Group × Hack-Nation × MIT "The VC Brain" challenge.

The core bet: *rank founders by **fit and demonstrated capability**, not fame or credentials* — and score the **cold-start founder** (no funding, no network, sometimes no GitHub) that the traditional pipeline misses.

## Pipeline

```
  Sourcing            Scoring                Screening         Decision
  ────────            ───────                ─────────         ────────
  GitHub  ┐           Founder Score          3 axes (not       Thesis fit
  ProductHunt ├─►  cold-start, coverage- ─►  averaged):    ─►  (ADVANCE/       ─► Evidence memo
  Hacker News │       weighted, power-law     Founder /         REVIEW/PASS)      w/ per-claim Trust
  (retrievers)┘       weights, confidence     Market /                            + data-completeness
                      bands                   Idea-vs-Market
                          │                                          │
                   cross-source dedup ─────────────────────────► export.py ─► FastAPI ─► React UI
                   (one Founder entity)                          (data contract)
```

- **Two-sided funnel:** *outbound* (we discover founders on GitHub/ProductHunt/HN) **and** *inbound* (a founder applies via the onboarding form → `POST /api/apply` → scored by the **same** pipeline, tagged `source_track=inbound`). If they give a GitHub handle we deep-read their code; otherwise the self-reported form scores thin, with an honestly wide confidence band.
- **Cold-start safe:** absence of a signal *widens the confidence band, never subtracts.* A brilliant repo with no network still scores — with honest uncertainty.
- **Multi-source, one axis:** GitHub (reads the actual code via LLM), ProductHunt & Hacker News (native signals: launches, organic upvotes, cadence). Same coverage-weighted `FounderScore`; GitHub is one input, not the gate.
- **Trust, not hallucination:** every memo claim traces to a source with a Trust level; missing data is flagged (`Cap table: not disclosed`), never invented.
- **Fairness by design:** pedigree / geography / age are weak soft priors, never gates; the reference class matches on *demonstrated building*, not credentials.

## Quickstart

```bash
# 1. Setup (Python 3.10+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add OPENAI_API_KEY / GITHUB_TOKEN to upgrade (optional)

# 2. Build the funnel from bundled sources (no keys needed)
python scripts/build_funnel.py

# 3. Serve it (rebuilds the deduped export, starts the API on :8000)
scripts/serve.sh

# 4. The UI (separate terminal) — talks to the API, falls back to mock if it's down
cd frontend && bun install && bun dev
```

Inspect from the terminal anytime:
```bash
python -m sourcing.store --thesis          # the ranked funnel through the fund lens
python -m sourcing.analyze <github_handle> # full decision packet for one founder
python scripts/smoke_test.py               # verify every API connection (5/5)
```

## Layout

| Path | What it is |
|---|---|
| `sourcing/` | **Intelligence layer** — `founder_score` (+ `capability`/`ambition`/`idea`), `native_score` (PH/HN), `inbound` (founder applications → same score), `screening` (3-axis), `thesis`, `memo`, `reference_class`, `identity` (dedup), `export`, `memory` (JSONL store). `analyze`/`store`/`bridge`/`hn_source` are CLIs. |
| `sourcing/retrievers/`, `sourcing/pipeline/` | **Collection toolkit** — one module per source (github/hn/producthunt/luma/twitter/linkedin/…) + enrichment pipeline. |
| `services/` | Earlier collection layer (fetchers + resolver). *See consolidation note below.* |
| `backend/` | **FastAPI** — serves the deduped scored founders to the UI in its `FounderProfile` shape. |
| `frontend/` | **React/TanStack UI** (dashboard, hunt, founder detail, thesis, memo). |
| `docs/` | `ARCHITECTURE.md`, `SCORING.md`, `FRONTEND_DATA.md` (the UI data contract). |
| `data/` | Append-only Memory store (signals, scores, screens) + `frontend_data.json`. |

## Known consolidation item (in progress)

Founder **collection** currently exists in three overlapping places — `sourcing/retrievers/` (canonical, most complete), `services/fetchers/`, and legacy collectors in `sourcing/`. The **intelligence layer** (scoring → screening → thesis → memo → export) is the single, unified path on top. Consolidating collection onto `retrievers/` is the outstanding cleanup; it does not affect the scoring/decision pipeline or the UI.
