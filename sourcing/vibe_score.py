"""Persistence-pattern scorer → founder-PROPENSITY band (brief deliverable 4).

The hard part of this brief: "shipped an app" is a WEAK signal. So this scorer
deliberately weights the PERSISTENCE PATTERN over the build itself, and it reads
the raw update timeline to earn every number:

  Recurrence     — distinct ships. A DECOY: toy-builders top this. Low weight.
  Iteration      — the SAME project getting repeated updates over weeks.
  User Response  — fixing things users complained about.
  Monetization   — waitlist / pricing: the "toy → maybe a thing" crossing.

The output is a PROPENSITY BAND with explicit uncertainty — never a confident
verdict (this is PREDICTION, Area of Research 3). It reuses the existing
`founder_score._aggregate`, so the band math is identical to the GitHub path.

Rule 2 (absence ≠ negative) is the crux and is done properly by distinguishing:
  * unknown          — we barely observed a timeline (sparse profile, or the real
                       snapshot source). LOW coverage → WIDENS the band. Not punished.
  * confirmed-absent — we DID observe an active timeline (many ships) and the
                       persistence events were genuinely zero. HIGH coverage, LOW
                       value → confidently low propensity. This is what defeats the
                       toy-builder decoy without punishing the cold-start unknown.

`as_of` re-scores using only signals before a date — the engine D5's retrospective
uses to show the band was already elevated BEFORE incorporation.

    python -m sourcing.vibe_score [real|synth|both]
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .founder_score import Component, _aggregate, _clamp
from . import vibe_schema as vs

_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(_ROOT, "data")
PROPENSITY_PATH = os.path.join(DATA_DIR, "propensity.jsonl")

DATASETS = {"real": "vibe_real.json", "synth": "vibe_synth.json"}

# Power-law weights for PROPENSITY: depth beats volume. Recurrence is downweighted
# precisely because it's the decoy the brief warns about.
VIBE_WEIGHTS = {"Recurrence": 0.7, "Iteration": 1.3, "User Response": 1.3, "Monetization": 1.5}
# coverage by observation state — the rule-2 lever.
COVERAGE = {vs.KNOWN: 1.0, vs.ABSENT: 0.9, vs.UNKNOWN: 0.1}


@dataclass
class Propensity:
    founder_id: str
    name: str
    handle: str
    propensity: float             # 0-100 point estimate
    confidence: float             # 0-1
    band: tuple                   # (low, high) — the honest range
    components: list              # list[Component]
    source: str = ""              # "real" | "synthetic"
    as_of: str | None = None
    caveat: str = ("Propensity band, not a verdict: predicts founder-intent from public building "
                   "behavior. Absence widens the band; it is never a penalty. Not a hiring/funding "
                   "decision on its own.")

    def band_str(self):
        return f"{self.band[0]:.0f}-{self.band[1]:.0f}"

    def to_dict(self):
        return {
            "founder_id": self.founder_id, "name": self.name, "handle": self.handle,
            "propensity": round(self.propensity, 1), "confidence": round(self.confidence, 3),
            "band": [round(self.band[0], 1), round(self.band[1], 1)],
            "components": [{"name": c.name, "value": round(c.value, 1),
                            "coverage": round(c.coverage, 3), "weight": c.weight,
                            "evidence": c.evidence, "note": c.note} for c in self.components],
            "source": self.source, "as_of": self.as_of, "caveat": self.caveat,
            "scored_at": vs.now(),
        }


def _state(count: int, n_updates_before: int) -> str:
    """Rule-2 core: distinguish 'observed absent' from 'don't know yet'."""
    if count > 0:
        return vs.KNOWN
    if n_updates_before >= 3:        # we saw an active timeline; the events were genuinely zero
        return vs.ABSENT
    return vs.UNKNOWN                # too little observed to say — widen, don't punish


def score_founder(f: dict, projects: list, as_of: str | None = None, source: str = "") -> Propensity:
    """Score one founder from their projects' raw update timelines."""
    def before(u):
        return (as_of is None) or (u.get("ts", "") <= as_of)

    updates = [u for p in projects for u in p.get("updates", []) if before(u)]
    ships = [p for p in projects if any(u["kind"] == "ship" and before(u) for u in p.get("updates", []))]
    n_before = len(updates)
    iters = [u for u in updates if u["kind"] in ("iterate", "fix_feedback")]
    fixes = [u for u in updates if u["kind"] == "fix_feedback"]
    mons = [u for u in updates if u["kind"] in ("waitlist", "pricing")]
    weeks = f.get("prior_track_record", {}).get("weeks_active", 0)

    def ev(items, kind_label):
        return [f"{u.get('note', kind_label)} — {u['url']}" for u in items[:3]]

    comps = []
    # Recurrence — always observed if there's a ship; the low-weight decoy.
    n_ships = len(ships)
    comps.append(Component(
        "Recurrence", _clamp(25 + 12 * min(n_ships, 6)), 1.0 if n_ships else 0.1,
        [f"{n_ships} distinct ship(s)" + (f" — {ships[0]['provenance_url']}" if ships else "")],
        note="decoy: volume alone doesn't predict founders"))

    # Iteration depth.
    st = _state(len(iters), n_before)
    val = _clamp(20 + 6 * min(len(iters), 12) + (10 if weeks >= 8 else 0)) if st != vs.UNKNOWN else 40
    comps.append(Component("Iteration", val, COVERAGE[st], ev(iters, "update"),
                           note=f"{len(iters)} update(s) over ~{weeks}w [{st}]"))

    # User response.
    st = _state(len(fixes), n_before)
    val = _clamp(25 + 15 * min(len(fixes), 5)) if st != vs.UNKNOWN else 40
    comps.append(Component("User Response", val, COVERAGE[st], ev(fixes, "fixed user-reported issue"),
                           note=f"{len(fixes)} fix(es) from user feedback [{st}]"))

    # Monetization attempt — the strongest crossing-the-line tell.
    st = _state(len(mons), n_before)
    val = (85 if mons else 15) if st != vs.UNKNOWN else 40
    comps.append(Component("Monetization", val, COVERAGE[st], ev(mons, "monetization step"),
                           note=("attempted" if mons else "none observed") + f" [{st}]"))

    for c in comps:
        c.weight = VIBE_WEIGHTS.get(c.name, 1.0)
    score, confidence, band = _aggregate(comps)
    return Propensity(
        founder_id=f["founder_id"], name=f["name"], handle=f.get("handles", {}).get("x", ""),
        propensity=score, confidence=confidence, band=band, components=comps,
        source=source, as_of=as_of)


# ── dataset plumbing ─────────────────────────────────────────────────────────

def load_dataset(name: str):
    path = os.path.join(DATA_DIR, DATASETS[name])
    data = json.load(open(path, encoding="utf-8"))
    by_founder = {}
    for p in data["projects"]:
        for fid in p["founder_ids"]:
            by_founder.setdefault(fid, []).append(p)
    return data["founders"], by_founder, ("synthetic" if name == "synth" else "real")


def score_dataset(name: str, persist: bool = True) -> list:
    founders, by_founder, source = load_dataset(name)
    out = [score_founder(f, by_founder.get(f["founder_id"], []), source=source) for f in founders]
    if persist:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PROPENSITY_PATH, "a", encoding="utf-8") as fh:
            for pr in out:
                fh.write(json.dumps(pr.to_dict(), ensure_ascii=False) + "\n")
    return out


def _validate(founders, scored):
    """Sanity check (NOT a scoring input): does propensity separate the ground-truth
    classes? Uses _ground_truth.became_founder, which the scorer never reads."""
    gt = {f["founder_id"]: f.get("_ground_truth", {}) for f in founders}
    pos = [p.propensity for p in scored if gt.get(p.founder_id, {}).get("became_founder")]
    neg = [p.propensity for p in scored if p.founder_id in gt and not gt[p.founder_id].get("became_founder")]
    if not pos or not neg:
        return None
    # rank-separation (AUC): P(random founder scores above random non-founder)
    wins = sum(1 for a in pos for b in neg if a > b) + 0.5 * sum(1 for a in pos for b in neg if a == b)
    auc = wins / (len(pos) * len(neg))
    return {"n_founder": len(pos), "n_not": len(neg),
            "mean_founder": sum(pos) / len(pos), "mean_not": sum(neg) / len(neg), "auc": auc}


def main(argv=None):
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    which = argv[0] if argv else "both"
    names = ["real", "synth"] if which == "both" else [which]

    for name in names:
        founders, _, _ = load_dataset(name)
        scored = score_dataset(name, persist=True)
        ranked = sorted(scored, key=lambda p: p.propensity, reverse=True)
        print(f"\n  ══ PROPENSITY — {name} ({len(ranked)} founders) ══")
        print(f"  {'founder':<20}{'handle':<18}{'propensity':>11}{'band':>12}{'conf':>7}")
        for p in ranked[:12]:
            print(f"  {p.name[:19]:<20}@{p.handle[:16]:<17}{p.propensity:>10.0f} "
                  f"{p.band_str():>11} {p.confidence:>6.0%}")
        v = _validate(founders, scored)
        if v:
            print(f"\n  validation (ground truth, NOT scored on): AUC {v['auc']:.2f}  ·  "
                  f"mean propensity founders {v['mean_founder']:.0f} vs non {v['mean_not']:.0f}  "
                  f"({v['n_founder']} vs {v['n_not']})")
        # show the decoy defeated: highest-recurrence founder and their propensity
        if name == "synth":
            top_recur = max(scored, key=lambda p: p.components[0].value)
            print(f"  decoy check: highest-recurrence builder '{top_recur.name}' "
                  f"(recurrence {top_recur.components[0].value:.0f}) → propensity {top_recur.propensity:.0f} "
                  f"band {top_recur.band_str()}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
