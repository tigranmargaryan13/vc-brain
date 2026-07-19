"""Real-source loader: Made with Lovable (madewithlovable.com).

Pulls a small sample of REAL vibe-coding builders to prove the population exists.
Chosen over Vibehackers.io because MwL is server-rendered (Vibehackers is a JS SPA
that returns an empty shell to a plain fetch) — the brief said pick the most
scrapeable, and to check structure first rather than assume an API. There is no
public API; the reliable structured source is the per-project schema.org JSON-LD
`SoftwareApplication` block on each /projects/<slug> page.

WHAT'S ACTUALLY PULLABLE (honest note — see module docstring in the PR):
  Per project, cleanly:  name, description (maker's own words), live product URL,
  categories, ship date (datePublished), price/offer, build-time label, stack.
  Maker identity: author.name + author X handle.
  Persistence signal we CAN derive from real data: BUILD RECURRENCE — group
  projects by the maker's X handle; a handle on ≥2 projects is a real repeat-ship.
  NOT in the real data (it's a snapshot gallery, not a build-in-public timeline):
  iteration depth (same project, repeated updates) and user-response signals.
  Those are seeded in the SYNTHETIC generator (D3) instead — stated plainly so the
  demo is honest about which signals are real vs synthesized.

TOS / CONSENT: this is public showcase data used for a hackathon prototype. In
production this must be consent-aware and ToS-compliant — we are profiling people
who did not opt into being scored. We cache locally and rate-limit to stay polite.

Stdlib only.

    python -m sourcing.vibe_source [n]      # pull ~n projects → data/vibe_real.json
"""
from __future__ import annotations

import html as htmllib
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

from . import vibe_schema as vs

BASE = "https://madewithlovable.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 vc-brain-research"}
_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(_ROOT, "data")
CACHE_DIR = os.path.join(DATA_DIR, ".vibe_cache")
OUT = os.path.join(DATA_DIR, "vibe_real.json")

RATE_LIMIT_S = 0.7   # polite: <1.5 req/s


def _fetch(url: str) -> str:
    """GET with an on-disk cache (polite + reproducible demos)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "_", url.lower())[-120:] + ".html"
    path = os.path.join(CACHE_DIR, key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    time.sleep(RATE_LIMIT_S)
    req = urllib.request.Request(url, headers=UA)
    body = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return body


def _iter_ld_objects(page: str):
    """Yield every schema.org object on the page (handles dict / list / @graph)."""
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if "@graph" in o and isinstance(o["@graph"], list):
                    stack.extend(o["@graph"])
                else:
                    yield o
            elif isinstance(o, list):
                stack.extend(o)


def _dl_fields(page: str) -> dict:
    """Parse the <dt>label</dt><dd>value</dd> spec table (Build time, Monetization, …)."""
    out = {}
    for dt, dd in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", page, re.S):
        label = htmllib.unescape(re.sub(r"<[^>]+>", "", dt)).strip()
        value = htmllib.unescape(re.sub(r"<[^>]+>", "", dd)).strip()
        if label:
            out[label] = value
    return out


def _handle_from_x(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"x\.com/@?([A-Za-z0-9_]+)", url)
    return m.group(1) if m else ""


def list_project_slugs(pages: int = 2) -> list[str]:
    slugs: list[str] = []
    seen = set()
    for p in range(1, pages + 1):
        page = _fetch(f"{BASE}/projects?page={p}" if p > 1 else f"{BASE}/projects")
        for s in re.findall(r"/projects/([a-z0-9][a-z0-9\-]+)", page):
            if s not in seen and s != "page":
                seen.add(s)
                slugs.append(s)
    return slugs


def fetch_project(slug: str) -> dict | None:
    """One project → a normalized raw record (still pre-scoring)."""
    url = f"{BASE}/projects/{slug}"
    page = _fetch(url)
    app = next((o for o in _iter_ld_objects(page) if o.get("@type") == "SoftwareApplication"), None)
    if not app:
        return None
    dl = _dl_fields(page)
    author = app.get("author") or {}
    price = ((app.get("offers") or {}).get("price"))
    return {
        "slug": slug,
        "provenance_url": url,
        "name": app.get("name") or slug,
        "description": app.get("description") or "",
        "product_link": app.get("installUrl") or app.get("url") or "",
        "categories": [c.strip() for c in (app.get("keywords") or "").split(",") if c.strip()],
        "date_published": app.get("datePublished") or "",
        "price": price,
        "price_currency": (app.get("offers") or {}).get("priceCurrency"),
        "maker_name": author.get("name") or "",
        "maker_handle": _handle_from_x(author.get("url", "")),
        "maker_url": author.get("url", ""),
        "build_time_label": dl.get("Build time", ""),
        "monetization_label": dl.get("Monetization", ""),
        "target_audience": dl.get("Target audience", ""),
        "stack": _stack_pills(page),
    }


def _stack_pills(page: str) -> list[str]:
    m = re.search(r"Stack detected(.*?)</div>\s*</div>", page, re.S)
    if not m:
        return []
    pills = re.findall(r">([A-Za-z0-9 .+_-]{2,30})</span>", m.group(1))
    return [htmllib.unescape(p).strip() for p in pills if p.strip()]


# ── assemble entities (many-to-many, claims baked in) ────────────────────────

def _monetization(rec: dict) -> dict:
    """Toy→'maybe a thing' tell. price>0 or a paid/waitlist label = an attempt."""
    label = (rec.get("monetization_label") or "").lower()
    price = rec.get("price")
    try:
        priced = float(price) > 0
    except (TypeError, ValueError):
        priced = False
    attempt = priced or any(k in label for k in ("paid", "subscription", "waitlist", "premium", "freemium"))
    state = "attempted" if attempt else ("free" if str(price) == "0" else "unknown")
    return {
        "state": state,
        "price": vs.observed({"amount": price, "currency": rec.get("price_currency")}, rec["provenance_url"])
                 if price is not None else None,
        "label": rec.get("monetization_label") or "",
    }


def build_entities(records: list[dict]) -> tuple[dict, dict]:
    """Group raw project records into Founder + Project entities, wired many-to-many.
    Grouping key = maker X handle (falls back to maker name)."""
    founders: dict[str, vs.Founder] = {}
    projects: dict[str, vs.Project] = {}

    for rec in records:
        key = rec["maker_handle"] or rec["maker_name"]
        if not key:
            continue  # can't attribute → skip (honest: no phantom founders)
        fid = vs.stable_id("fnd", key)
        f = founders.get(fid)
        if not f:
            f = vs.Founder(
                founder_id=fid,
                name=rec["maker_name"] or rec["maker_handle"],
                handles={"x": rec["maker_handle"]} if rec["maker_handle"] else {},
                source="madewithlovable",
                profile_url=rec["maker_url"] or f"{BASE}/projects/{rec['slug']}",
            )
            founders[fid] = f

        pid = vs.stable_id("prj", rec["slug"])
        mon = _monetization(rec)
        proj = vs.Project(
            startup_id=pid,
            name=rec["name"],
            slug=rec["slug"],
            problem=vs.claim(rec["description"][:400], rec["provenance_url"], confidence=0.4),
            solution_description=vs.claim(rec["description"], rec["provenance_url"], confidence=0.4),
            product_link=rec["product_link"],
            provenance_url=rec["provenance_url"],
            categories=rec["categories"],
            stack=rec["stack"] or ["Lovable"],
            first_seen=rec["date_published"],
            updates=[{"ts": rec["date_published"], "kind": "ship",
                      "url": rec["provenance_url"], "source": "madewithlovable"}],
            monetization=mon,
            startup_stage="prototype",
            data_gaps=["iteration history not disclosed by source (snapshot gallery)",
                       "user-response signals not observable on this source"],
        )
        # public_footprint signal (traceable)
        f.public_footprint.append(vs.footprint_signal(
            "ship", {"project": rec["name"], "date": rec["date_published"],
                     "stack": proj.stack, "monetization": mon["state"]},
            rec["provenance_url"], observed_at=rec["date_published"] or None))
        vs.link(f, proj)
        projects[pid] = proj

    # derive founder-level rollups (build recurrence = the one real persistence signal)
    for f in founders.values():
        ships = [projects[pid] for pid in f.project_ids]
        n = len(ships)
        dates = sorted(d for d in (p.first_seen for p in ships) if d)
        f.prior_track_record = {
            "projects_shipped": n,
            "serial_builder": vs.observed(n >= 2, f.profile_url) if n >= 2 else vs.claim(False, f.profile_url, 0.5),
            "first_ship": dates[0] if dates else "",
            "latest_ship": dates[-1] if dates else "",
        }
        attempts = [p for p in ships if p.monetization.get("state") == "attempted"]
        f.intent_signals = {
            "build_recurrence": vs.observed(n, f.profile_url),  # ≥2 distinct ships is the real tell
            "monetization_attempt": (vs.observed(True, attempts[0].provenance_url)
                                     if attempts else vs.claim(False, f.profile_url, 0.5)),
        }
        f.skills = sorted({s for p in ships for s in p.stack} |
                          {c for p in ships for c in p.categories})
        f.data_completeness = {
            "x_handle": vs.field_state(f.handles.get("x")),
            "build_recurrence": vs.KNOWN,                       # we counted real ships
            "iteration_depth": vs.UNKNOWN,                      # snapshot source — not observable
            "user_response": vs.UNKNOWN,
            "monetization": vs.KNOWN if attempts else vs.UNKNOWN,
        }
    return founders, projects


def collect(n: int = 20, pages: int | None = None) -> dict:
    # ~58% of MwL projects list no maker, so over-fetch slugs to net ~n founders.
    pages = pages or max(3, (n // 8) + 2)
    slugs = list_project_slugs(pages=pages)
    records = []
    for s in slugs:
        r = fetch_project(s)
        if r and (r["maker_handle"] or r["maker_name"]):
            records.append(r)
        if len({(x["maker_handle"] or x["maker_name"]) for x in records}) >= n:
            break
    founders, projects = build_entities(records)
    return {
        "generated_at": vs.now(),
        "source": "madewithlovable.com",
        "note": ("Real vibe-coding builders. Build-recurrence is real (grouped by maker X handle); "
                 "iteration-depth and user-response are NOT observable on this snapshot source and "
                 "are seeded synthetically in D3."),
        "founders": [f.__dict__ for f in founders.values()],
        "projects": [p.__dict__ for p in projects.values()],
    }


def main(argv=None):
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    n = int(argv[0]) if argv else 20
    data = collect(n=n)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    fs, ps = data["founders"], data["projects"]
    repeat = [f for f in fs if f["prior_track_record"]["projects_shipped"] >= 2]
    print(f"\n  wrote {OUT}")
    print(f"  {len(ps)} real projects → {len(fs)} distinct makers  "
          f"({len(repeat)} with ≥2 ships = real build-recurrence)")
    for f in sorted(fs, key=lambda x: -x["prior_track_record"]["projects_shipped"])[:8]:
        n_ships = f["prior_track_record"]["projects_shipped"]
        print(f"    · {f['name'][:22]:<22} @{f['handles'].get('x','—'):<18} {n_ships} ship(s)")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
