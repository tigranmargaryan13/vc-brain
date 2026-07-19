"""Synthetic profile generator — seeds the persistence-pattern signals that the
real snapshot source (Made with Lovable) cannot expose: iteration depth, user
response, and monetization timelines, spread over weeks.

WHY SYNTHETIC (and why it's honest): the hard part of this brief is that "shipped
an app" is a WEAK signal — vibe coding made shipping trivial, so the false-positive
rate is brutal. To show a scorer can separate the persistence pattern from the
noise, we need labelled cases with KNOWN outcomes and KNOWN timelines. Real data
gives us neither cheaply. So we synthesize a spread of archetypes, seed a few as
"went on to found a company" and a few as "prolific builder who didn't," and store
the outcome as GROUND TRUTH (never read by the scorer — see `_ground_truth`, an
underscored, leakage-safe field used only for D5 validation).

Every synthetic signal is tagged `source_id="synthetic"` so the demo can visibly
distinguish real provenance from seeded provenance — the honesty guardrail.

Deterministic (seeded RNG, fixed date anchor) so demos reproduce exactly.

    python -m sourcing.vibe_synth [n]     # ~n synthetic profiles → data/vibe_synth.json

Archetypes (the separable spread):
  future_founder  — persists: deep iteration + responds to users + monetizes, THEN
                    incorporates. Signals fire BEFORE the incorporation_date.
  toy_builder     — the false positive: ships MANY weekend toys, zero persistence.
  one_hit_quitter — one ship, abandoned. Low everything.
  steady_iterator — the honest middle: real iteration, some monetize — mixed outcomes.
  sparse          — one ship, everything else unknown. Tests absence≠negative: must
                    get a WIDE band, not a low score.
"""
from __future__ import annotations

import json
import os
import random
from datetime import date, timedelta

from . import vibe_schema as vs

_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(_ROOT, "data")
OUT = os.path.join(DATA_DIR, "vibe_synth.json")

ANCHOR = date(2026, 7, 19)   # "today" — fixed for reproducibility
SRC = "synthetic"

# ── content pools (kept small but varied; enough for believable evidence) ────
_FIRST = ["Maya", "Diego", "Aisha", "Tom", "Lena", "Ravi", "Sofia", "Jae", "Nadia",
          "Omar", "Priya", "Ben", "Yuki", "Clara", "Mateo", "Hana", "Ivan", "Zoe",
          "Kofi", "Elif", "Noah", "Ana", "Sam", "Wei", "Lucas"]
_LAST = ["Okafor", "Ramos", "Khan", "Feld", "Berg", "Nair", "Costa", "Park", "Aziz",
         "Haddad", "Iyer", "Cole", "Sato", "Nowak", "Silva", "Vogel", "Popov", "Reyes"]
_PRODUCT = ["Flowly", "Drafta", "Nudge", "Cohortly", "Snippd", "Ledgerly", "Mendo",
            "Quill", "Loopin", "Trackr", "Pantry", "Beacon", "Formly", "Cueup", "Stashr",
            "Relay", "Mapster", "Habita", "Vetta", "Chorus", "Bindr", "Tallyo", "Pingly"]
_CATS = ["Artificial Intelligence", "Developer Tools", "Productivity", "Fintech",
         "Health & Fitness", "E-Commerce", "Education", "Marketing", "Design Tools"]
_STACKS = ["Lovable", "Bolt", "v0", "Cursor", "Replit"]
_TECH = ["Supabase", "Next.js", "React", "Postgres", "OpenAI", "Stripe", "Tailwind"]
_PROBLEMS = [
    "teams waste hours copy-pasting {x} between tools",
    "indie sellers can't afford a data person to clean their {x}",
    "students have no clear map from {x} to a first job",
    "small clinics still track {x} on paper",
    "creators lose track of {x} across five apps",
    "founders re-build the same {x} boilerplate every launch",
]
_NOUNS = ["invoices", "leads", "catalogs", "workouts", "study plans", "changelogs",
          "receipts", "shifts", "recipes", "bookings"]
_FEATURES = ["added CSV import", "shipped a dark mode", "rebuilt onboarding",
             "added team workspaces", "sped up load time 3x", "added an API",
             "shipped mobile layout", "added templates"]
_COMPLAINTS = ["export was broken for large files", "sign-up kept 500ing",
               "no way to undo a delete", "mobile was unusable", "slow on big datasets",
               "confusing empty state", "lost data on refresh"]


def _iso(d: date) -> str:
    return d.isoformat()


def _handle(rng, first, last):
    return f"{first.lower()}{rng.choice(['', last.lower(), str(rng.randint(2, 89))])}"[:20] or first.lower()


def _domain(name):
    return f"https://{name.lower()}.app"


def _post_url(handle, rng):
    return f"https://x.com/{handle}/status/{rng.randint(10**17, 9*10**17)}"


# ── timeline construction per archetype ──────────────────────────────────────

def _timeline(archetype, rng, start: date, handle, product):
    """Return (updates[], monetization dict, weeks_active, incorporation_date|None)."""
    dom = _domain(product)
    updates = [{"ts": _iso(start), "kind": "ship", "url": f"{dom}",
                "note": f"shipped {product}", "source": SRC}]
    mon = {"state": "free", "price": None, "label": ""}
    inc = None

    def add(kind, d, note, url):
        updates.append({"ts": _iso(d), "kind": kind, "url": url, "note": note, "source": SRC})

    if archetype == "future_founder":
        n_iter = rng.randint(6, 11)
        for i in range(n_iter):
            d = start + timedelta(days=4 + i * rng.randint(4, 9))
            if d >= ANCHOR:
                break
            if rng.random() < 0.4:
                c = rng.choice(_COMPLAINTS)
                add("fix_feedback", d, f"fixed: {c} (user-reported)", _post_url(handle, rng))
            else:
                add("iterate", d, rng.choice(_FEATURES), f"{dom}/changelog#{i+1}")
        # monetization: waitlist → pricing, then incorporate a few weeks later
        wl = start + timedelta(days=rng.randint(35, 60))
        pr = wl + timedelta(days=rng.randint(14, 30))
        if wl < ANCHOR:
            add("waitlist", wl, "opened a waitlist", f"{dom}/waitlist")
        if pr < ANCHOR:
            add("pricing", pr, "added paid plans (Stripe)", f"{dom}/pricing")
            mon = {"state": "attempted", "price": vs.observed({"amount": rng.choice([9, 19, 29]),
                   "currency": "USD"}, f"{dom}/pricing"), "label": "Paid"}
            inc = pr + timedelta(days=rng.randint(14, 42))
            inc = inc if inc < ANCHOR else None

    elif archetype == "toy_builder":
        pass  # single ship per project, no iteration/response/monetization (the false positive)

    elif archetype == "one_hit_quitter":
        if rng.random() < 0.6:
            d = start + timedelta(days=rng.randint(3, 9))
            if d < ANCHOR:
                add("iterate", d, rng.choice(_FEATURES), f"{dom}/changelog#1")

    elif archetype == "steady_iterator":
        n_iter = rng.randint(3, 7)
        for i in range(n_iter):
            d = start + timedelta(days=6 + i * rng.randint(6, 12))
            if d >= ANCHOR:
                break
            if rng.random() < 0.3:
                add("fix_feedback", d, f"fixed: {rng.choice(_COMPLAINTS)}", _post_url(handle, rng))
            else:
                add("iterate", d, rng.choice(_FEATURES), f"{dom}/changelog#{i+1}")
        if rng.random() < 0.5:
            wl = start + timedelta(days=rng.randint(30, 55))
            if wl < ANCHOR:
                add("waitlist", wl, "opened a waitlist", f"{dom}/waitlist")
                mon = {"state": "attempted", "price": None, "label": "Waitlist"}
                if rng.random() < 0.5:                       # ~half of these become founders
                    inc = wl + timedelta(days=rng.randint(20, 50))
                    inc = inc if inc < ANCHOR else None

    # sparse: nothing beyond the ship

    weeks = max(1, ((max(date.fromisoformat(u["ts"]) for u in updates) -
                     date.fromisoformat(updates[0]["ts"])).days) // 7)
    return updates, mon, weeks, inc


# ── entity assembly ──────────────────────────────────────────────────────────

def _make_project(rng, founder, product, archetype, start):
    handle = founder.handles.get("x", "")
    updates, mon, weeks, inc = _timeline(archetype, rng, start, handle, product)
    prob = rng.choice(_PROBLEMS).format(x=rng.choice(_NOUNS))
    dom = _domain(product)
    cats = rng.sample(_CATS, k=rng.randint(1, 3))
    stack = [rng.choice(_STACKS)] + rng.sample(_TECH, k=rng.randint(1, 3))
    if mon["state"] == "attempted" and "Stripe" not in stack:
        stack.append("Stripe")
    pid = vs.stable_id("prj", f"{founder.founder_id}-{product}")
    proj = vs.Project(
        startup_id=pid,
        name=product,
        slug=product.lower(),
        problem=vs.claim(prob, updates[0]["url"], confidence=0.4),
        solution_description=vs.claim(f"{product} — {prob}. Built with {stack[0]}.",
                                      updates[0]["url"], confidence=0.4),
        product_link=dom,
        provenance_url=updates[0]["url"],
        categories=cats,
        stack=stack,
        first_seen=updates[0]["ts"],
        updates=updates,
        monetization=mon,
        startup_stage="prototype" if mon["state"] != "attempted" else "early",
        data_gaps=[] if len(updates) > 1 else ["single ship — no iteration observed"],
    )
    return proj, inc, weeks


def _rollup(founder, projects):
    """Compute persistence rollups + completeness from the timelines (traceable)."""
    all_updates = [(p, u) for p in projects for u in p.updates]
    n_proj = len(projects)
    iterate_events = [u for _, u in all_updates if u["kind"] in ("iterate", "fix_feedback")]
    fix_events = [u for _, u in all_updates if u["kind"] == "fix_feedback"]
    mon_events = [u for _, u in all_updates if u["kind"] in ("waitlist", "pricing")]
    weeks_active = 0
    if all_updates:
        ds = [date.fromisoformat(u["ts"]) for _, u in all_updates]
        weeks_active = max(1, (max(ds) - min(ds)).days // 7)
    dates = sorted(p.first_seen for p in projects if p.first_seen)

    founder.prior_track_record = {
        "projects_shipped": n_proj,
        "serial_builder": vs.observed(n_proj >= 2, founder.profile_url),
        "first_ship": dates[0] if dates else "",
        "latest_ship": dates[-1] if dates else "",
        "weeks_active": weeks_active,
    }
    founder.intent_signals = {
        "build_recurrence": vs.observed(n_proj, founder.profile_url),
        "iteration_depth": vs.observed(len(iterate_events), founder.profile_url),
        "user_response": vs.observed(len(fix_events),
                                     fix_events[0]["url"] if fix_events else founder.profile_url),
        "monetization_attempt": vs.observed(bool(mon_events),
                                            mon_events[-1]["url"] if mon_events else founder.profile_url),
    }
    founder.skills = sorted({s for p in projects for s in p.stack} |
                            {c for p in projects for c in p.categories})
    founder.public_footprint = [
        vs.footprint_signal(u["kind"], {"project": p.name, "note": u.get("note", "")},
                            u["url"], observed_at=u["ts"], source_id=SRC)
        for p, u in all_updates
    ]
    founder.data_completeness = {
        "x_handle": vs.field_state(founder.handles.get("x")),
        "build_recurrence": vs.KNOWN,
        "iteration_depth": vs.KNOWN if iterate_events else vs.ABSENT,   # checked timeline, none found
        "user_response": vs.KNOWN if fix_events else vs.ABSENT,
        "monetization": vs.KNOWN if mon_events else vs.ABSENT,
    }
    # sparse founders: we did NOT observe a timeline → unknown, not confirmed-absent
    if n_proj == 1 and len(projects[0].updates) == 1:
        founder.data_completeness.update({"iteration_depth": vs.UNKNOWN,
                                          "user_response": vs.UNKNOWN,
                                          "monetization": vs.UNKNOWN})


def _seed_contradiction(rng, founder, projects):
    """Seed a self-reported KPI that conflicts with the observed timeline — gives the
    Trust/contradiction machinery something real to flag (rule #1 in action)."""
    p = projects[0]
    claimed = rng.choice([1500, 3000, 8000])
    engaged = len([u for u in p.updates if u["kind"] == "fix_feedback"])
    contra = []
    if engaged == 0:   # claims big users but shows zero user-response activity
        contra = [f"observed timeline shows no user-response events (0 fixes) for {p.name}"]
    p.traction_kpis = {
        "users": {
            "claimed": vs.claim(claimed, _post_url(founder.handles.get("x", "x"), rng),
                                confidence=0.35, contradicts=contra),
            "verified": None,
        }
    }
    if contra:
        p.trust_scores.append({"claim": f"{claimed} users (self-reported)",
                               "status": "contradiction", "contradicts": contra})


def _founder(rng, idx, archetype):
    first, last = rng.choice(_FIRST), rng.choice(_LAST)
    name = f"{first} {last}"
    handle = _handle(rng, first, last)
    fid = vs.stable_id("fnd", f"synthetic-{idx}-{handle}")
    f = vs.Founder(founder_id=fid, name=name, handles={"x": handle},
                   source=SRC, profile_url=f"https://x.com/{handle}")

    n_projects = {"future_founder": rng.randint(1, 2), "toy_builder": rng.randint(5, 9),
                  "one_hit_quitter": 1, "steady_iterator": 1, "sparse": 1}[archetype]
    projects, incs = [], []
    used = set()
    for j in range(n_projects):
        product = rng.choice([p for p in _PRODUCT if p not in used] or _PRODUCT)
        used.add(product)
        start = ANCHOR - timedelta(weeks=rng.randint(6, 22))
        # for toy builders, ships are scattered but each shallow
        proj, inc, _ = _make_project(rng, f, product, archetype, start)
        projects.append(proj)
        vs.link(f, proj)
        if inc:
            incs.append(inc)
    _rollup(f, projects)

    became = archetype == "future_founder" or (archetype == "steady_iterator" and bool(incs))
    incorporation = min(incs).isoformat() if (became and incs) else None
    # future_founder always incorporates even if the timeline clipped the pricing event
    if archetype == "future_founder" and not incorporation:
        incorporation = (ANCHOR - timedelta(weeks=rng.randint(1, 4))).isoformat()
        became = True

    ground_truth = {
        "archetype": archetype,
        "became_founder": became,
        "incorporation_date": incorporation,   # for D5 retrospective ONLY
    }
    # seed a contradiction on ~1 in 4 non-persisters that "claim" traction
    if archetype in ("toy_builder", "steady_iterator") and rng.random() < 0.5:
        _seed_contradiction(rng, f, projects)
    return f, projects, ground_truth


_MIX = (["future_founder"] * 8 + ["toy_builder"] * 10 + ["one_hit_quitter"] * 9 +
        ["steady_iterator"] * 15 + ["sparse"] * 8)   # 50


def build_dataset(n: int = 50, seed: int = 7) -> dict:
    rng = random.Random(seed)
    mix = (_MIX * ((n // len(_MIX)) + 1))[:n]
    rng.shuffle(mix)
    founders, projects, truth = [], [], {}
    for i, arch in enumerate(mix):
        f, ps, gt = _founder(rng, i, arch)
        f_dict = f.__dict__
        f_dict["_ground_truth"] = gt          # leakage-safe: underscored, not a scoring input
        founders.append(f_dict)
        projects.extend(p.__dict__ for p in ps)
        truth[f.founder_id] = gt
    n_founder = sum(1 for g in truth.values() if g["became_founder"])
    return {
        "generated_at": vs.now(),
        "source": SRC,
        "note": ("Synthetic. Persistence timelines (iteration/user-response/monetization) are SEEDED. "
                 "_ground_truth.became_founder is the validation label — the scorer must NOT read it."),
        "counts": {"founders": len(founders), "projects": len(projects),
                   "became_founder": n_founder, "did_not": len(founders) - n_founder},
        "founders": founders,
        "projects": projects,
    }


def main(argv=None):
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    n = int(argv[0]) if argv else 50
    data = build_dataset(n=n)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    c = data["counts"]
    print(f"\n  wrote {OUT}")
    print(f"  {c['founders']} synthetic founders · {c['projects']} projects · "
          f"{c['became_founder']} became founders / {c['did_not']} did not")
    from collections import Counter
    arch = Counter(g["_ground_truth"]["archetype"] for g in data["founders"])
    print("  archetypes:", dict(arch))
    # show one future_founder timeline as a sanity check
    ff = next(g for g in data["founders"] if g["_ground_truth"]["archetype"] == "future_founder")
    print(f"\n  sample future_founder: {ff['name']} @{ff['handles']['x']} "
          f"(incorporated {ff['_ground_truth']['incorporation_date']})")
    print(f"    recurrence={ff['intent_signals']['build_recurrence']['value']} "
          f"iteration={ff['intent_signals']['iteration_depth']['value']} "
          f"user_response={ff['intent_signals']['user_response']['value']} "
          f"monetization={ff['intent_signals']['monetization_attempt']['value']}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
