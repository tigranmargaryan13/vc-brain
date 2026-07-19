# VC Brain — Sourcing Architecture

> The most heavily-weighted, least-commercially-solved pillar. The design goal is not
> "scan more channels" — it's to **detect founders before they are visibly founders**, and
> to **score the ones with no track record at all**. Everything below is built around those
> two edges, because that is where the rubric puts the points.

---

## 1. Design principles

1. **Leading over lagging.** Trending repos, YC badges, Show HN front pages are lagging
   indicators — by the time they fire, the "find them first" edge is gone and network bias is
   baked in. We treat those as table stakes and spend our depth on signals that fire *earlier*.
2. **Capability over credential.** A founder is scoreable from what they can *demonstrably do*
   (read their code, their competition standings, their project ambition), not from who funded
   or employed them. This is what makes cold-start work.
3. **Absence is not a penalty.** No funding / no network / no press must not zero a founder out.
   Missing signals widen the confidence interval; they do not subtract from the score.
   (If we get this wrong, we've just rebuilt the network-gated system the challenge exists to kill.)
4. **One funnel, many collectors.** Inbound applications and outbound-discovered founders converge
   into the *same* scored pipeline. Channels are pluggable; the scoring core is shared.
5. **Every number cites its evidence.** Each score component links to the exact signal that drove
   it (supports Trust Score + the Agentic Traceability stretch goal).
6. **The graph learns.** Channels are scored by the *quality* of what they produce (funded deals),
   not volume — and scan budget follows yield (stretch goal 3).

---

## 2. Pipeline overview

```
                         ┌─────────────────────────────────────────────┐
   OUTBOUND collectors → │                                             │
   (scan the world)      │   RAW SIGNAL LOG  (append-only, never drop)  │
                         │   dedup · timestamp · tag by source          │
   INBOUND application → │                                             │
   (deck + company name) └───────────────────┬─────────────────────────┘
                                             │
                                    ENTITY RESOLUTION
                            (GitHub + X + LinkedIn + email → one Person)
                                             │
                                    ┌────────▼─────────┐
                                    │  FOUNDER SCORE    │  persists in Memory,
                                    │  (cold-start safe)│  never resets, trends over time
                                    └────────┬─────────┘
                                             │
                              THESIS FILTER (sector/stage/geo/check/risk)
                                             │
                                     RANKED FUNNEL
                                    ┌────────┴─────────┐
                          below threshold        above threshold
                               (park)          → ACTIVATE (cold outreach → real application)
                                                      │
                                                converts → funded?
                                                      │
                                        CHANNEL-YIELD FEEDBACK LOOP
                                     (reweight scan budget toward quality)
```

---

## 3. Collector framework

Every channel implements one interface and emits normalized signals. This is what makes the
system *extensible* rather than a pile of one-off scrapers — a judge should be able to see that
adding a new channel is a ~50-line plugin, not a rewrite.

```python
class Collector(Protocol):
    source_id: str          # "hn_comments", "stealth_detector", ...
    tier: int               # 0 table-stakes, 1 leading, 2 capability, 3 graph/reflexive
    cadence: str            # "realtime" | "hourly" | "daily"
    def collect(self, since: datetime) -> list[RawSignal]: ...

@dataclass
class RawSignal:
    source_id: str
    entity_handles: dict     # {"github": "...", "x": "...", "email": "...", "name": "..."}
    signal_type: str         # "stealth_transition", "insightful_comment", "repo_quality", ...
    payload: dict            # structured, source-specific
    url: str                 # provenance — the exact link the signal came from
    observed_at: datetime
```

### Collector registry (build priority)

| Tier | Collector | Fires on | Emits | Build effort |
|---|---|---|---|---|
| **1** | **Stealth / quitting detector** | LinkedIn/X profile delta → "stealth" / "building something" / senior role left, no new employer | `stealth_transition` | Med — the flagship leading signal |
| **1** | **HN comment-quality miner** | Unusually sharp comment on a hard technical thread (via HN Algolia API) | `insightful_comment` | Low — API is free & rich |
| **2** | **Repo reader** | Any GitHub identity in the funnel | `repo_quality` (LLM reads architecture/tests/commit discipline) | Med — the cold-start engine |
| **2** | **Competition standings** | Kaggle / Codeforces / AoC ranks | `competitive_rank` | Low |
| **3** | **Founder referral ("who should be a founder but isn't?")** | Activated founder names a peer | `peer_referral` | Low — attacks cold-start directly |
| **3** | **Diaspora tracker** | Departures from founder-factory companies (Stripe/Palantir/DeepMind/breakout YC) | `diaspora_move` | Med |
| **0** | GitHub trending / new orgs | Repo velocity | `repo_trending` | Low (table stakes) |
| **0** | ProductHunt / Devpost (all submissions) | Launch / hackathon submission | `launch`, `hackathon_submission` | Low |
| **0** | arXiv / patents | New paper / individual inventor | `research_output` | Low |
| **0** | Accelerator cohorts + **rejections** | Batch lists | `accelerator_signal` | Low |

> Build the **bolded tier-1/2/3 rows deep**; wire tier-0 shallow so the funnel is complete but
> don't spend your best hours there.

---

## 4. Data model (Memory layer)

Append-only signal log + resolved entities + versioned scores. Nothing is discarded; the log is
what lets us show **trend over time**, not just the latest snapshot.

```
signals        (id, source_id, signal_type, entity_id?, payload, url, observed_at, ingested_at)
entities       (id, canonical_name, handles jsonb, first_seen, last_updated)
handle_links   (entity_id, kind, value, confidence)          -- resolution evidence
founder_scores (entity_id, component, value, confidence, evidence_signal_ids[], scored_at)
applications   (id, entity_id, source: inbound|activated, deck_uri, company_name, status)
channel_yield  (source_id, signals, activated, applied, funded, quality_score, updated_at)
```

Entity resolution = deterministic handle match first (same GitHub/email/domain), then
LLM-assisted fuzzy merge (same name + overlapping bio/links) with a stored confidence. Merges are
reversible because the raw log is never mutated.

---

## 5. Founder Score (cold-start safe)

Persists in Memory, never resets, follows the *person* across companies. It is **one input into
the per-opportunity Founder axis**, not a replacement for it.

Four components, each scored **0–100 with a coverage/confidence weight**:

| Component | Sources | Cold-start behavior |
|---|---|---|
| **Capability** | repo_quality, competitive_rank, hackathon_submission, research_output | **Primary driver when nothing else exists.** Works from raw output alone. |
| **Trajectory** | commit/posting velocity & acceleration, learning-in-public cadence | Fires for anyone building, funded or not. |
| **Provenance** | diaspora_move, peer_referral, OSS co-contribution graph | Degrades gracefully to 0 coverage — **never negative**. |
| **Traction** | launch, users, revenue (if any) | Absent for early founders → low *coverage*, not low *score*. |

**Aggregation rule (the important bit):**

```
score      = Σ (component_value × coverage_i) / Σ coverage_i     # coverage-weighted, not fixed-weight
confidence = f(total coverage, corroboration across sources)      # wide interval when data is thin
```

- A cold-start founder with a brilliant repo and nothing else gets a **high Capability score with a
  wide confidence band** — surfaced for review, honestly flagged as uncertain. This is the
  behavior the rubric's Q10/Q11 are testing for.
- Confidence bands are the concrete stab at Area-of-Research #1 (prediction intervals around soft
  assessments) — we don't claim precision we don't have.

Every component stores `evidence_signal_ids[]` → the memo can cite the exact repo/comment/rank that
moved the number (Trust Score + traceability).

---

## 6. Activation

Above-threshold outbound candidates get **cold outreach, not cold investment** — the goal is to
trigger a real application into the same Screening step as inbound.

- Personalized reach-out references the *specific* signal we found ("your commit history on X /
  your HN comment on Y") — proves the system actually saw them, not spray-and-pray.
- Optional **async work-sample** at this step: a tiny prove-it prompt. Their response becomes a
  fresh `repo_quality`-style capability signal — turning outreach into more data either way.

---

## 7. Channel-yield feedback loop (stretch goal 3)

Instrument every channel end-to-end: `signals → activated → applied → funded`. The channel's
`quality_score` is a function of **funded conversions, time-decayed**, not raw volume. Scan budget
(cadence, rate limits, LLM spend) is reallocated toward high-yield channels each cycle, and the
system proactively surfaces *underexplored* channels that are punching above their volume.

This is a lead-scoring / channel-attribution problem — cheap to prototype, and it's the difference
between "a scraper" and "a system that gets smarter."

---

## 8. Hackathon build sequence

1. **Signal log + entity resolution + one tier-0 collector** (GitHub) — prove the spine end-to-end.
2. **Repo reader → Founder Score with coverage-weighting** — the cold-start differentiator. Demo:
   score a founder with *only* a repo and show the honest wide confidence band.
3. **One tier-1 leading collector** — HN comment miner (fastest) or stealth detector (flashiest).
4. **Activation** with signal-specific outreach copy.
5. **Channel-yield loop** — even a thin version reads as self-improving.
6. Backfill remaining tier-0 collectors shallowly so the funnel looks complete.

Depth on 2 + 3 is what wins; 1/4/5/6 make it a coherent system.
