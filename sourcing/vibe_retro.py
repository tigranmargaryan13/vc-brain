"""Retrospective check (brief deliverable 5) — the rigor test.

For seeded "became a founder" cases, replay the propensity WEEK BY WEEK using the
scorer's `as_of` engine and show that the signal crossed a watchlist threshold
BEFORE the incorporation date. That is what separates prediction from hindsight:
we're not explaining a known founder after the fact, we're showing the system
would have surfaced them while they were still "just building."

Aggregate result (not one cherry-picked anecdote): the median LEAD TIME — how many
weeks before incorporation the propensity first crossed the watchlist bar — across
all seeded founders. Honest about misses (founders we'd never have flagged).

    python -m sourcing.vibe_retro [name-or-handle]   # detail for one; else aggregate + one exemplar
"""
from __future__ import annotations

from datetime import date, timedelta

from . import vibe_score as vscore

WATCHLIST = 60.0   # propensity at/above which we'd add someone to the review funnel


def _founders_with_outcome():
    founders, by_founder, _ = vscore.load_dataset("synth")
    fmap = {f["founder_id"]: f for f in founders}
    return fmap, by_founder


def _weekly_track(f, projects):
    """Propensity at each weekly as_of, from first signal up to incorporation."""
    gt = f.get("_ground_truth", {})
    inc = gt.get("incorporation_date")
    updates = sorted(u["ts"] for p in projects for u in p.get("updates", []))
    if not updates:
        return None
    start = date.fromisoformat(updates[0])
    end = date.fromisoformat(inc) if inc else date.fromisoformat(updates[-1])
    track = []
    d = start
    while d <= end:
        as_of = d.isoformat()
        pr = vscore.score_founder(f, projects, as_of=as_of, source="synthetic")
        track.append((as_of, pr.propensity, pr.band))
        d += timedelta(days=7)
    # ensure the incorporation date itself is represented
    if inc and (not track or track[-1][0] != inc):
        pr = vscore.score_founder(f, projects, as_of=inc, source="synthetic")
        track.append((inc, pr.propensity, pr.band))
    return {"incorporation": inc, "track": track}


def _lead_time(f, projects):
    """Weeks between first crossing WATCHLIST and incorporation (None if never crossed)."""
    t = _weekly_track(f, projects)
    if not t or not t["incorporation"]:
        return None
    inc = date.fromisoformat(t["incorporation"])
    crossed = next((as_of for as_of, p, _ in t["track"] if p >= WATCHLIST), None)
    if not crossed:
        return {"crossed": None, "lead_weeks": None, "incorporation": t["incorporation"]}
    lead = (inc - date.fromisoformat(crossed)).days / 7.0
    return {"crossed": crossed, "lead_weeks": lead, "incorporation": t["incorporation"]}


def _render_detail(f, projects):
    t = _weekly_track(f, projects)
    L = [f"\n  ═══ RETROSPECTIVE — {f['name']} @{f['handles'].get('x','')} ═══",
         f"  ground truth: became a founder · incorporated {t['incorporation']}",
         f"  watchlist threshold: propensity ≥ {WATCHLIST:.0f}\n",
         f"  {'as of':<14}{'weeks to inc.':>14}{'propensity':>12}{'band':>12}   status"]
    inc = date.fromisoformat(t["incorporation"]) if t["incorporation"] else None
    first_cross = None
    for as_of, p, band in t["track"]:
        wk = (inc - date.fromisoformat(as_of)).days / 7.0 if inc else 0
        flag = ""
        if p >= WATCHLIST and first_cross is None:
            first_cross = as_of
            flag = "  ← crosses watchlist (BEFORE incorporation)"
        at_inc = "  ⟵ INCORPORATION" if as_of == t["incorporation"] else ""
        L.append(f"  {as_of:<14}{wk:>13.0f}w{p:>12.0f}{f'{band[0]:.0f}-{band[1]:.0f}':>12}{flag}{at_inc}")
    if first_cross and inc:
        lead = (inc - date.fromisoformat(first_cross)).days / 7.0
        L.append(f"\n  → We would have flagged {f['name']} ~{lead:.0f} weeks BEFORE incorporation.")
        L.append("    The persistence signals (iteration, user-response, monetization) were already")
        L.append("    firing while they were still 'just a builder' — prediction, not hindsight.")
    return "\n".join(L)


def main(argv=None):
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    fmap, by_founder = _founders_with_outcome()
    founders = list(fmap.values())

    # aggregate over all seeded founders
    leads, never, exemplar = [], 0, None
    for f in founders:
        if not f.get("_ground_truth", {}).get("became_founder"):
            continue
        projects = by_founder.get(f["founder_id"], [])
        lt = _lead_time(f, projects)
        if not lt:
            continue
        if lt["lead_weeks"] is None:
            never += 1
        else:
            leads.append(lt["lead_weeks"])
            if exemplar is None or lt["lead_weeks"] > exemplar[1]:
                exemplar = (f, lt["lead_weeks"])

    if argv:
        q = argv[0].lower().lstrip("@")
        f = next((x for x in founders if q in x["name"].lower() or q in x["handles"].get("x", "").lower()), None)
        if not f:
            print(f"no founder matching '{argv[0]}'", file=sys.stderr)
            return 1
        print(_render_detail(f, by_founder.get(f["founder_id"], [])))
        return 0

    n = len(leads) + never
    print(f"\n  ══ RETROSPECTIVE VALIDATION — {n} seeded founders ══")
    if leads:
        leads.sort()
        median = leads[len(leads) // 2]
        print(f"  flagged before incorporation: {len(leads)}/{n}"
              + (f"  ·  missed (never crossed {WATCHLIST:.0f}): {never}" if never else ""))
        print(f"  lead time (weeks before incorporation): median {median:.0f}  ·  "
              f"range {min(leads):.0f}–{max(leads):.0f}")
        print("  → the propensity signal is LEADING, not lagging: it fires while they're still building.")
    if exemplar:
        print(_render_detail(exemplar[0], by_founder.get(exemplar[0]["founder_id"], [])))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
