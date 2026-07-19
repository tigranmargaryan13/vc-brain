#!/usr/bin/env python3
"""Build the UI dataset (data/ui/sourced_founders.json) consumed at runtime by
the Lovable app (FounderProfile[] shape, see frontend src/lib/mock-data.ts).

v2 — roster comes from founder_product_info.csv (all rows). Real pipeline
outputs are joined in wherever they exist:
  - founder scores/components:  python -m sourcing.export  (Memory store)
  - 3-axis screens (market / idea-vs-market stances + trends)
Missing fields are filled with SEEDED random values (stable across reruns) so
every card renders complete — per team decision for the demo (2026-07-19).

Run:  python3 scripts/build_ui_dataset.py
(it auto-runs `python -m sourcing.export` to refresh pipeline joins)
"""
import csv, hashlib, json, os, random, re, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(REPO, "founder_product_info.csv")
OUT = os.path.join(REPO, "data", "ui", "sourced_founders.json")
EXPORT = os.path.join(tempfile.gettempdir(), "vcbrain_frontend_data.json")

SECTORS = ["AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer",
           "Deep Tech", "Biotech", "Cybersecurity", "SaaS"]
STAGES = ["Pre-seed", "Seed", "Series A"]
CITIES = ["Berlin", "London", "Paris", "Amsterdam", "Lisbon", "San Francisco",
          "New York", "Tokyo", "Nairobi", "Lagos", "Mexico City"]

SECTOR_MAP = [
    (["artificial intelligence", "ai", "machine learning", "gpt", "llm", "bots"], "AI/ML"),
    (["developer tools", "software engineering", "github", "api", "open source", "development"], "Dev Tools"),
    (["fintech", "finance", "payments", "crypto", "investing"], "Fintech"),
    (["health", "fitness", "medical"], "Healthtech"),
    (["security", "privacy"], "Cybersecurity"),
    (["climate", "energy"], "Climate"),
    (["hardware", "robotics", "3d printer", "maker", "space"], "Deep Tech"),
    (["biotech"], "Biotech"),
    (["e-commerce", "social", "twitter", "education", "travel", "games", "music", "dating"], "Consumer"),
    (["saas", "productivity", "marketing", "sales", "analytics", "design tools", "business intelligence", "data"], "SaaS"),
]
EXPORT_SECTOR = {"ai infra": "AI/ML", "developer tools": "Dev Tools", "data": "SaaS",
                 "systems": "Deep Tech"}
MARKET = {"bullish": "Bullish", "neutral": "Neutral", "bear": "Bear"}
FIT = {"survives": "Survives as-is", "pivot-capable": "Pivot potential",
       "market-carried": "Pivot potential", "weak": "At risk"}
TREND = {"improving": "up", "declining": "down", "stable": "flat", "new": "flat"}


def rng_for(name):
    return random.Random(int(hashlib.md5(name.encode()).hexdigest(), 16))


def map_sector(industry, export_sector, rng):
    for part in re.split(r"[;,]", industry or ""):
        pl = part.strip().lower()
        for keys, sector in SECTOR_MAP:
            if pl and any(k in pl for k in keys):
                return sector
    if export_sector and export_sector in EXPORT_SECTOR:
        return EXPORT_SECTOR[export_sector]
    return rng.choice(SECTORS)


def norm_location(raw, rng):
    loc = re.sub(r"\s*\(tz\)\s*$", "", (raw or "").strip())
    loc = loc.split(",")[0].strip()
    return loc if loc else rng.choice(CITIES)


def handle_of(row):
    m = re.search(r"producthunt\.com/@([A-Za-z0-9_.-]+)", row.get("profile_url") or "")
    return m.group(1) if m else None


def load_export():
    try:
        subprocess.run([sys.executable, "-m", "sourcing.export", EXPORT],
                       cwd=REPO, check=True, capture_output=True, timeout=120)
    except Exception:
        pass
    try:
        d = json.load(open(EXPORT))
    except Exception:
        return {}, {}
    by_handle, by_name = {}, {}
    for f in d.get("founders", []):
        by_handle[(f.get("handle") or "").lower()] = f
        by_name[(f.get("name") or "").strip().lower()] = f
    return by_handle, by_name


def main():
    rows = list(csv.DictReader(open(CSV)))
    by_handle, by_name = load_export()
    out, used = [], set()

    for row in rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        rng = rng_for(name)
        handle = handle_of(row)
        fv = (by_handle.get((handle or "").lower())
              or by_name.get(name.lower()))

        uid = re.sub(r"[^a-z0-9_]+", "_", (handle or name).lower()).strip("_") or f"f{len(out)}"
        if uid in used:
            uid = f"{uid}_{len(out)}"
        used.add(uid)

        product = (row.get("product_company") or "").strip() or f"{name.split()[0]}'s venture"
        one = re.sub(r"\s+", " ", (row.get("product_overview") or "").strip())
        if len(one) > 110:
            one = one[:107].rstrip() + "…"

        # --- scores: real pipeline values when joined, seeded-random otherwise ---
        if fv:
            founder_score = max(1, min(round(fv["founder_score"]["value"]), 100))
            sc = fv.get("screen") or {}
            market = MARKET.get((sc.get("market") or {}).get("stance"), "Neutral")
            fit = FIT.get((sc.get("idea_vs_market") or {}).get("stance"), "Pivot potential")
            f_tr = TREND.get((sc.get("founder") or {}).get("trend"), "flat")
            m_tr = TREND.get((sc.get("market") or {}).get("trend"), "flat")
            i_tr = TREND.get((sc.get("idea_vs_market") or {}).get("trend"), "flat")
        else:
            founder_score = rng.randint(48, 85)
            market = rng.choices(["Bullish", "Neutral", "Bear"], weights=[3, 5, 2])[0]
            fit = rng.choices(["Survives as-is", "Pivot potential", "At risk"], weights=[3, 5, 2])[0]
            f_tr, m_tr, i_tr = (rng.choice(["up", "flat", "flat", "down"]) for _ in range(3))

        # --- evidence: only real, citable facts get source links ---
        E = []
        ph = row.get("profile_url") or "https://www.producthunt.com"
        def ev(text, trust, state, url, label):
            E.append({"text": text, "trust": trust, "state": state,
                      "sourceUrl": url, "sourceLabel": label})

        if fv:
            band = fv["founder_score"].get("band") or []
            band_s = f" (90% band {band[0]:.0f}–{band[1]:.0f})" if len(band) == 2 else ""
            ev(f"VC Brain pipeline Founder Score {fv['founder_score']['value']:.1f}{band_s}, "
               f"confidence {fv['founder_score'].get('confidence', 0):.2f}.",
               "High", "corroborated", fv.get("profile_url") or ph, "VC Brain pipeline")
            for comp in (fv["founder_score"].get("components") or [])[:2]:
                for e_txt in (comp.get("evidence") or [])[:1]:
                    ev(f"{comp['name']}: {e_txt}"[:160], "Medium", "corroborated",
                       fv.get("profile_url") or ph, "VC Brain pipeline")
        up = (row.get("upvotes") or "").strip()
        if up.isdigit() and int(up) > 0:
            ev(f"{up} upvotes on the latest Product Hunt launch ({row.get('launched') or 'recent'}).",
               "High", "corroborated", row.get("product_url") or ph, "Product Hunt")
        cm = (row.get("comments") or "").strip()
        if cm.isdigit() and int(cm) > 0:
            ev(f"{cm} community comments on the launch.", "Medium", "corroborated",
               row.get("product_url") or ph, "Product Hunt")
        hn = (row.get("hn_points") or "").strip()
        if hn.isdigit() and int(hn) > 0:
            ev(f"{hn} points on Hacker News.", "High", "corroborated",
               "https://news.ycombinator.com", "Hacker News")
        if (row.get("fresh_domain") or "").strip().lower() in ("true", "1", "yes"):
            ev("Freshly registered domain — early intent signal.", "Medium", "corroborated",
               row.get("website") or ph, "Domain records")
        gh_url = (row.get("github_url") or "").strip()
        if gh_url.startswith("http"):
            ev("Public GitHub profile.", "Medium", "corroborated", gh_url, "GitHub")
        li = (row.get("linkedin") or "").strip()
        if li.startswith("http"):
            ev("Public LinkedIn profile.", "Medium", "corroborated", li, "LinkedIn")
        site = (row.get("website") or "").strip()
        if site.startswith("http"):
            ev("Live product website.", "Medium", "corroborated", site, "Website")
        if (row.get("description") or "").strip():
            d = re.sub(r"\s+", " ", row["description"].strip())
            ev(f"Product description: {d[:120]}", "Medium", "uncorroborated",
               row.get("product_url") or ph, "Product Hunt")
        if row.get("source") == "dinner":
            ev("Attended a curated NYC founders dinner (invite-based).", "Medium",
               "corroborated", ph, "Luma")

        contradictions = (fv or {}).get("memo", {}).get("contradictions") or []

        rec = {
            "id": f"src_{uid}",
            "name": name,
            "email": f"{uid}@vcbrain.example",
            "location": norm_location(row.get("location"), rng),
            "projects": [{
                "id": f"src_{uid}_p1",
                "name": product,
                "sector": map_sector(row.get("industry"), (fv or {}).get("sector"), rng),
                "stage": rng.choice(STAGES),
                "oneLiner": one or f"Building {product}.",
            }],
            "scores": {
                "founder": founder_score,
                "founderTrend": f_tr,
                "market": market,
                "marketTrend": m_tr,
                "fit": fit,
                "fitTrend": i_tr,
            },
            "evidence": E,
        }
        if contradictions:
            rec["hasContradiction"] = True
        out.append(rec)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    joined = sum(1 for r in out if any(e["sourceLabel"] == "VC Brain pipeline" for e in r["evidence"]))
    sectors = {}
    for r in out:
        sectors[r["projects"][0]["sector"]] = sectors.get(r["projects"][0]["sector"], 0) + 1
    print(f"founders: {len(out)} | real pipeline scores: {joined} | contradictions: "
          f"{sum(1 for r in out if r.get('hasContradiction'))}")
    print("sectors:", sectors)
    print("scores:", min(r["scores"]["founder"] for r in out), "-",
          max(r["scores"]["founder"] for r in out))


if __name__ == "__main__":
    main()
