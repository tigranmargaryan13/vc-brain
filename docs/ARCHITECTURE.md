# VC Brain — architecture & consistency guide

Two bodies of code were built in parallel and are now **one layered pipeline**.
This doc is the contract that keeps them consistent — read it before adding code.

```
        INGESTION (services/)                 INTELLIGENCE (sourcing/)
  ┌────────────────────────────┐        ┌──────────────────────────────────┐
  │ fetchers/  (github, hn,     │        │ github_collector  (deep read)     │
  │            producthunt,     │        │ founder_score  (coverage-weighted)│
  │            crunchbase)      │        │ screening  (3 axes, not averaged) │
  │ resolver/  (dedup → people) │──────▶ │ thesis · reference_class · memo   │
  └────────────────────────────┘  seam  │ memory  (append-only JSONL store) │
        raw signals → people            └──────────────────────────────────┘
                     │                                    │
                     └──────────  sourcing/bridge.py  ──┘
                        (resolve candidates → score each GitHub identity)
```

- **Ingestion — `services/`** (teammate): multi-source fetchers + the entity
  resolver (union-find over shared identifiers + fuzzy name → unique people).
  Uses `requests` / `rapidfuzz` / `python-dotenv`.
- **Intelligence — `sourcing/`**: the scoring/analysis pipeline. Stdlib-only
  (plus optional `openai`), independently runnable.
- **Seam — `sourcing/bridge.py`**: the only module that bridges the two.
  `resolve_identity(candidates)` → for each person's GitHub handle →
  `score_github_handle`. Run: `python -m sourcing.bridge <handle> ...`

## Conventions — how to stay consistent

1. **One GitHub client.** All GitHub HTTP goes through
   `sourcing/github_collector.py` (`public_repos()` for lists, `collect()` for
   the deep read). `services/fetchers/github_fetcher.py` is a thin adapter that
   **delegates** to it — do not add a second GitHub client.
2. **One store, for now: JSONL** (`sourcing/memory.py`, `data/*.jsonl`). The SQL
   schema in `db/migrations/0001_init.sql` is the **documented target** for the
   Founder/Startup/Claim entities in [../vc_brain_criteria_and_schema.md](../vc_brain_criteria_and_schema.md);
   migrate to Postgres only when there's time. Whichever store, field names must
   match that schema doc so data flows between layers.
3. **One env file.** Everything reads the git-ignored `.env`. `services/` uses
   `python-dotenv` (`load_dotenv()`); `sourcing/` auto-loads it in
   `sourcing/__init__.py`. Same variable names: `OPENAI_API_KEY`, `GITHUB_TOKEN`,
   `CRUNCHBASE_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`. Keep `.env.example` in sync.
4. **Deps in `requirements.txt`.** `pip install -r requirements.txt`. `sourcing/`
   stays importable without them (only `pipeline.py` needs `services/` deps).
5. **Verify with the smoke test.** `python scripts/smoke_test.py` checks every
   API + the resolver. Keep it green.

## Status (what's real vs. stub)

| Piece | State |
|---|---|
| `services/fetchers/{github,hn}` , `services/resolver/resolver.py` | ✅ implemented |
| `services/scoring/`, `services/fetchers/{producthunt_fetcher,fetcher_worker}`, `services/resolver/heuristics.py` | 🗑️ removed — empty stubs superseded by `sourcing/` (scoring) and `sourcing/retrievers/` (collection) |
| `db/` (`init_db.py` + empty `0001_init.sql`) | ⛔ unused — the store is JSONL (`data/`); the SQL layer is a documented target. Kept pending a team decision. |
| `sourcing/*` (score, native_score, screen, thesis, memo, reference_class, identity, memory, export, bridge) | ✅ implemented, tested |
| `backend/` (FastAPI) + `frontend/` (UI wired to it) | ✅ implemented |

## Open items to keep consistency

- **Commit `sourcing/`** — it's currently untracked (not shared, at risk).
- **Resolve the scoring overlap** — `services/scoring/` is empty; `sourcing/founder_score.py` is the real scorer. Pick one home.
- **Write `0001_init.sql`** to the schema doc (or formally declare JSONL the store of record for the hackathon).
- **Feed real candidates through the seam** — wire a fetcher (e.g. HN) → resolver → `pipeline.run()` so the funnel fills from discovery, not just typed handles.
