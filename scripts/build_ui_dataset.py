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
import csv, hashlib, json, math, os, random, re, subprocess, sys, tempfile

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

# docs/SCORING.md — the seven Founder Score components and their power-law weights
WEIGHTS = {"Capability": 1.3, "Skills": 1.0, "Trajectory": 1.0, "Ceiling": 1.5,
           "Intent": 1.2, "Provenance": 0.8, "Traction": 1.0}

SKILL_POOL = ["Python", "TypeScript", "React", "LLM orchestration", "Data pipelines",
              "Go", "Rust", "Product design", "Growth", "DevOps", "SQL", "APIs"]


def aggregate_dims(dims):
    """Exact combine step from docs/SCORING.md (_aggregate)."""
    num = sum(d["value"] * d["coverage"] * d["weight"] for d in dims)
    den = sum(d["coverage"] * d["weight"] for d in dims)
    score = (num / den) if den else 0.0
    avg_cov = sum(d["coverage"] for d in dims) / len(dims)
    corrob = sum(1 for d in dims if d["coverage"] > 0.15)
    conf = max(0.10, min(0.95, 0.25 + 0.55 * avg_cov + 0.04 * corrob))
    margin = (1 - conf) * 35
    band = [round(max(0.0, score - margin), 1), round(min(100.0, score + margin), 1)]
    return round(score), round(conf, 2), band


def dim(name, value, coverage):
    return {"name": name, "value": round(max(0, min(100, value))),
            "coverage": round(max(0.0, min(1.0, coverage)), 2),
            "weight": WEIGHTS[name]}


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

        # --- dimensions per docs/SCORING.md: real pipeline components when joined,
        # derived from CSV signals otherwise (seeded-random only where data is absent) ---
        upvotes_n = int(row["upvotes"]) if (row.get("upvotes") or "").strip().isdigit() else 0
        comments_n = int(row["comments"]) if (row.get("comments") or "").strip().isdigit() else 0
        tags = [t.strip() for t in re.split(r"[;,]", row.get("industry") or "") if t.strip()]
        overview_len = len((row.get("product_overview") or "") + (row.get("description") or ""))
        fresh = (row.get("fresh_domain") or "").strip().lower() in ("true", "1", "yes")

        if fv and fv.get("founder_score", {}).get("components"):
            dims = [dim(c["name"], c.get("value", 0), c.get("coverage", 0))
                    for c in fv["founder_score"]["components"] if c.get("name") in WEIGHTS]
            for missing in WEIGHTS.keys() - {d["name"] for d in dims}:
                dims.append(dim(missing, 0, 0.0))
            founder_score = max(1, min(round(fv["founder_score"]["value"]), 100))
            confidence = round(fv["founder_score"].get("confidence", 0.5), 2)
            b = fv["founder_score"].get("band") or []
            band = [round(b[0], 1), round(b[1], 1)] if len(b) == 2 else \
                [max(0, founder_score - 20), min(100, founder_score + 20)]
        else:
            dims = [
                dim("Capability", rng.randint(45, 85), rng.uniform(0.3, 0.7)),
                dim("Skills", 30 + 12 * len(tags), min(1.0, len(tags) / 4)),
                dim("Trajectory", rng.randint(40, 80), rng.uniform(0.2, 0.6)),
                dim("Ceiling", rng.randint(45, 90), min(1.0, 0.3 + overview_len / 2000)),
                dim("Intent", 70 if fresh else rng.randint(30, 60),
                    0.5 if fresh else rng.uniform(0.1, 0.3)),
                dim("Provenance", 50 if row.get("source") == "dinner" else rng.randint(20, 50),
                    0.33 if row.get("source") == "dinner" else 0.0),
                dim("Traction", min(100, round(upvotes_n * 0.4)),
                    min(1.0, (upvotes_n + comments_n) / 200)),
            ]
            founder_score, confidence, band = aggregate_dims(dims)

        if fv:
            sc = fv.get("screen") or {}
            market = MARKET.get((sc.get("market") or {}).get("stance"), "Neutral")
            fit = FIT.get((sc.get("idea_vs_market") or {}).get("stance"), "Pivot potential")
            f_tr = TREND.get((sc.get("founder") or {}).get("trend"), "flat")
            m_tr = TREND.get((sc.get("market") or {}).get("trend"), "flat")
            i_tr = TREND.get((sc.get("idea_vs_market") or {}).get("trend"), "flat")
        else:
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

        # --- completeness: share of CSV fields actually filled (drives UI ordering) ---
        COMPLETENESS_FIELDS = ["product_company", "product_overview", "description",
                               "industry", "upvotes", "comments", "launched",
                               "domain_age_days", "fresh_domain", "hn_points",
                               "location", "github_username", "linkedin", "website",
                               "product_url"]
        filled = sum(1 for k in COMPLETENESS_FIELDS if (row.get(k) or "").strip())
        completeness = round(filled / len(COMPLETENESS_FIELDS) * 100)

        # --- details: every real CSV field, passed through for the profile page ---
        details = {"source": "NYC founders dinner" if row.get("source") == "dinner"
                   else "Product Hunt"}
        if (row.get("launched") or "").strip():
            details["launched"] = row["launched"].strip()
        for csv_k, det_k in (("upvotes", "upvotes"), ("comments", "comments"),
                             ("hn_points", "hnPoints"), ("domain_age_days", "domainAgeDays")):
            v = (row.get(csv_k) or "").strip()
            if v.isdigit():
                details[det_k] = int(v)
        if (row.get("fresh_domain") or "").strip().lower() in ("true", "1", "yes"):
            details["freshDomain"] = True
        if (row.get("industry") or "").strip():
            details["industry"] = row["industry"].strip()
        links = []
        for label, url in (("Product Hunt", row.get("profile_url")),
                           ("Launch", row.get("product_url")),
                           ("GitHub", row.get("github_url")),
                           ("LinkedIn", row.get("linkedin")),
                           ("Website", row.get("website"))):
            u = (url or "").strip()
            if u.startswith("http"):
                links.append({"label": label, "url": u})
        if links:
            details["links"] = links

        # --- enrichment: bio, skills, contact, full project description ---
        location = norm_location(row.get("location"), rng)
        desc_full = re.sub(r"\s+", " ", ((row.get("product_overview") or "") + " " +
                                         (row.get("description") or "")).strip())
        bio = (f"{name.split()[0]} is building {product}"
               + (f" — {desc_full[:180].rstrip('.')}." if desc_full else ".")
               + f" Based in {location}."
               + (" Sourced via a curated NYC founders dinner." if row.get("source") == "dinner"
                  else " Discovered via Product Hunt launch signals."))
        skills = tags[:4] + [s for s in rng.sample(SKILL_POOL, 4) if s not in tags]
        skills = skills[:5]
        li_url = (row.get("linkedin") or "").strip()
        contact = {
            "email": f"{uid}@vcbrain.example",
            "linkedin": li_url if li_url.startswith("http")
            else f"https://www.linkedin.com/in/{uid.replace('_', '-')}",
        }
        if (row.get("website") or "").strip().startswith("http"):
            contact["website"] = row["website"].strip()

        rec = {
            "id": f"src_{uid}",
            "name": name,
            "email": f"{uid}@vcbrain.example",
            "location": location,
            "completeness": completeness,
            "bio": bio,
            "skills": skills,
            "contact": contact,
            "details": details,
            "dimensions": dims,
            "projects": [{
                "id": f"src_{uid}_p1",
                "name": product,
                "sector": map_sector(row.get("industry"), (fv or {}).get("sector"), rng),
                "stage": rng.choice(STAGES),
                "oneLiner": one or f"Building {product}.",
                "description": desc_full or f"{product} — details to be confirmed on founder call.",
            }],
            "scores": {
                "founder": founder_score,
                "founderTrend": f_tr,
                "market": market,
                "marketTrend": m_tr,
                "fit": fit,
                "fitTrend": i_tr,
                "confidence": confidence,
                "band": band,
            },
            "evidence": E,
        }
        if contradictions:
            rec["hasContradiction"] = True
        out.append(rec)

    # ---- arXiv — academic-paper channel (pre-founding researchers, cold-start) ----
    # Signals from scripts/fetch_arxiv_founders.py (same criterion contract as the
    # ProductHunt signals). Real citable facts only — no seeded fills; stage is
    # "Pre-seed" by definition of the channel, unknowns are flagged, not invented.
    # ---- Academic sourcing channel (academic_founders.csv — 4-channel pipeline,
    # real founder_score + founder_potential; supersedes the legacy arXiv set) ----
    VERTICAL = {"ai infrastructure": "AI/ML", "robotics": "Deep Tech",
                "climate / energy": "Climate", "healthcare": "Healthtech",
                "cybersecurity": "Cybersecurity"}
    acad_rows = []
    try:
        acad_rows = [r for r in csv.DictReader(open(f"{REPO}/academic_founders.csv"))
                     if (r.get("name") or "").strip()]
    except FileNotFoundError:
        pass

    def _i(row, key):
        v = (row.get(key) or "").strip()
        try:
            return int(float(v))
        except ValueError:
            return 0

    for row in acad_rows:
        name = row["name"].strip()
        rng = rng_for(name)
        gh = (row.get("github_handle") or "").strip()
        fv = by_handle.get(gh.lower()) if gh else None  # real pipeline join
        uid = re.sub(r"[^a-z0-9_]+", "_", (gh or name).lower()).strip("_")
        if not uid or uid in used:
            continue
        used.add(uid)

        stars, forks = _i(row, "repo_stars"), _i(row, "repo_forks")
        cadence = _i(row, "publication_cadence_12mo")
        cites = _i(row, "author_citations_total")
        hidx = _i(row, "author_h_index")
        repos = _i(row, "builder_public_repos")
        potential = _i(row, "founder_potential")
        aff = (row.get("affiliation") or row.get("industry_affiliation") or "").strip()
        code_url = (row.get("code_url") or "").strip()
        paper_url = (row.get("paper_url") or "https://arxiv.org").strip()
        title = (row.get("paper_title") or "Untitled paper").strip()
        intent_txt = (row.get("founder_intent") or row.get("pre_founding_status") or "").lower()
        has_intent = bool(intent_txt) and "no founder markers" not in intent_txt
        vertical = (row.get("market_vertical") or "").strip().lower()
        domain = (row.get("domain") or "").lower()
        sector = VERTICAL.get(vertical) or ("Cybersecurity" if "cs.cr" in domain
                  else "Deep Tech" if "cs.ro" in domain
                  else "Biotech" if "q-bio" in domain else "AI/ML")

        if fv and fv.get("founder_score", {}).get("components"):
            # real pipeline scoring (sourcing/ SCORING.md engine) — same as PH rows
            dims = [dim(c["name"], c.get("value", 0), c.get("coverage", 0))
                    for c in fv["founder_score"]["components"] if c.get("name") in WEIGHTS]
            for missing in WEIGHTS.keys() - {d["name"] for d in dims}:
                dims.append(dim(missing, 0, 0.0))
            a_score = max(1, min(round(fv["founder_score"]["value"]), 100))
            a_conf = round(fv["founder_score"].get("confidence", 0.5), 2)
            b = fv["founder_score"].get("band") or []
            a_band = [round(b[0], 1), round(b[1], 1)] if len(b) == 2 else \
                [max(0, a_score - 20), min(100, a_score + 20)]
        else:
            dims = [
                dim("Capability", min(100, 40 + stars // 5 + (20 if code_url else 0)),
                    0.5 if code_url else 0.15),
                dim("Skills", min(100, 30 + repos * 3), min(1.0, repos / 10)),
                dim("Trajectory", min(100, 30 + cadence * 3),
                    min(1.0, (cadence + (1 if code_url else 0)) / 8)),
                dim("Ceiling", potential or rng.randint(40, 70), 0.6 if potential else 0.2),
                dim("Intent", 65 if has_intent else 35, 0.4 if has_intent else 0.15),
                dim("Provenance", (25 if aff else 0) + min(50, _i(row, "coauthors") * 5),
                    0.33 if aff else 0.1),
                dim("Traction", min(100, stars * 2 + forks * 3),
                    min(1.0, (stars + forks) / 10)),
            ]
            agg_score, a_conf, a_band = aggregate_dims(dims)
            a_score = max(1, min(_i(row, "founder_score") or agg_score, 100))
            margin = (a_band[1] - a_band[0]) / 2
            a_band = [round(max(0.0, a_score - margin), 1), round(min(100.0, a_score + margin), 1)]

        proj = (code_url.rstrip("/").rsplit("/", 1)[-1] if code_url
                else f"Research: {title[:40]}")
        E = []
        def aev2(text, trust, state, url, label):
            E.append({"text": text, "trust": trust, "state": state,
                      "sourceUrl": url, "sourceLabel": label})
        if fv:
            bnd = fv["founder_score"].get("band") or []
            band_s = f" (90% band {bnd[0]:.0f}–{bnd[1]:.0f})" if len(bnd) == 2 else ""
            aev2(f"VC Brain pipeline read their GitHub code: Founder Score "
                 f"{fv['founder_score']['value']:.1f}{band_s}, confidence "
                 f"{fv['founder_score'].get('confidence', 0):.2f}.",
                 "High", "corroborated",
                 fv.get("profile_url") or f"https://github.com/{gh}", "VC Brain pipeline")
        aev2(f"First-author paper: {title[:110]}", "High", "corroborated", paper_url, "arXiv")
        aev2(f"VC Brain founder-potential assessment: {potential}/100." if potential
             else "Founder-potential assessment pending.", "Medium", "corroborated",
             paper_url, "VC Brain pipeline")
        if code_url:
            aev2("Code released with the paper.", "High", "corroborated", code_url, "GitHub")
        if stars or forks:
            aev2(f"Repo traction: {stars} stars, {forks} forks.", "High", "corroborated",
                 code_url or paper_url, "GitHub")
        if cadence:
            aev2(f"{cadence} papers in the last 12 months.", "Medium", "corroborated",
                 paper_url, "arXiv")
        if cites or hidx:
            aev2(f"Author impact: {cites} citations, h-index {hidx}.", "High",
                 "corroborated", paper_url, "Semantic Scholar")
        if aff:
            aev2(f"Affiliation: {aff}.", "Medium", "corroborated", paper_url, "arXiv")
        if has_intent:
            aev2(f"Founder-intent signal: {intent_txt[:100]}.", "Medium", "uncorroborated",
                 paper_url, "VC Brain pipeline")

        links = [{"label": "arXiv", "url": paper_url}]
        if code_url:
            links.append({"label": "Code", "url": code_url})
        if gh:
            links.append({"label": "GitHub", "url": f"https://github.com/{gh}"})
        a_filled = sum(1 for k in ("paper_title", "code_url", "github_handle", "repo_stars",
                                   "author_citations_total", "affiliation", "founder_potential",
                                   "publication_cadence_12mo", "market_vertical", "domain")
                       if (row.get(k) or "").strip())
        out.append({
            "id": f"acad_{uid}",
            "name": name,
            "email": f"{uid}@vcbrain.example",
            "location": rng.choice(CITIES),
            "completeness": round(a_filled / 10 * 100),
            "bio": (f"{name.split()[0]} is a researcher building in {sector}"
                    + (f" ({aff})" if aff else "")
                    + f" — first-author of \"{title[:100]}\". Sourced via the academic channel."),
            "skills": ["Research", "Machine Learning"] + [d.strip().upper() for d in domain.split(";")[:2] if d.strip()],
            "contact": {"email": f"{uid}@vcbrain.example",
                        **({"website": code_url} if code_url else {}),
                        "linkedin": f"https://www.linkedin.com/in/{uid.replace('_', '-')}"},
            "details": {"source": "Academic sourcing", "links": links,
                        **({"industry": row.get("domain")} if (row.get("domain") or "").strip() else {})},
            "dimensions": dims,
            "projects": [{
                "id": f"acad_{uid}_p1",
                "name": proj,
                "sector": sector,
                "stage": "Pre-seed",
                "oneLiner": title if len(title) <= 110 else title[:107].rstrip() + "…",
                "description": f"Academic work: {title}. "
                               + (f"Open-source implementation at {code_url}. " if code_url else "")
                               + "Pre-founding — sourced by the academic pipeline (arXiv + GitHub + potential assessment).",
            }],
            "scores": {
                "founder": a_score,
                "founderTrend": "up" if cadence >= 6 else "flat",
                "market": rng.choices(["Bullish", "Neutral", "Bear"], weights=[3, 5, 2])[0],
                "marketTrend": "flat",
                "fit": "Pivot potential",
                "fitTrend": "flat",
                "confidence": a_conf,
                "band": a_band,
            },
            **({"coldStart": True} if (row.get("cold_start") or "").strip().lower() == "true" else {}),
            "evidence": E,
        })

    # legacy arXiv channel — only used when the academic dataset is absent
    try:
        arxiv_rows = [] if acad_rows else json.load(open(f"{REPO}/arxiv_founder_signals.json"))
    except FileNotFoundError:
        arxiv_rows = []
    for arec in arxiv_rows:
        fo, pa, sig = arec["founder"], arec.get("paper") or {}, arec.get("signals") or {}
        name = (fo.get("name") or "").strip()
        if not name:
            continue
        uid = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
        if not uid or uid in used:
            continue
        used.add(uid)

        def aval(key):
            s = sig.get(key) or {}
            return s.get("value"), s.get("citation")

        abs_url = pa.get("url") or "https://arxiv.org"
        code_url = pa.get("code_url")
        cadence, cad_cit = aval("publication_cadence_12mo")
        cites, cites_cit = aval("earned_attention_citations")
        coauthors, coa_cit = aval("coauthor_network")
        aff, aff_cit = aval("industry_affiliation")
        cadence = int(cadence or 0)
        coauthors = int(coauthors or 0)

        # positive-only additive heuristic (cold-start rule: absence adds nothing)
        score = 35 + 6 + (8 if code_url else 0) + min(cadence * 2, 12)
        if cites is not None:
            score += min(int(math.log10(int(cites) + 1) * 6), 12)
        if aff:
            score += 4
        score = max(35, min(score, 95))

        title = pa.get("title") or "Untitled paper"
        one = title if len(title) <= 110 else title[:107].rstrip() + "…"
        cats = " ".join(pa.get("categories") or []).lower()
        sector = ("Deep Tech" if "cs.ro" in cats else
                  "Cybersecurity" if "cs.cr" in cats else
                  "Biotech" if "q-bio" in cats else "AI/ML")
        project = (code_url.rstrip("/").rsplit("/", 1)[-1] if code_url
                   else f"arXiv:{pa.get('arxiv_id')}")

        E = []
        def aev(text, trust, state, url, label, unknown=False):
            item = {"text": text, "trust": trust, "state": state,
                    "sourceUrl": url, "sourceLabel": label}
            if unknown:
                item["unknown"] = True
            E.append(item)

        aev(f"First-author paper ({pa.get('published')}): {title[:100]}",
            "High", "corroborated", abs_url, "arXiv")
        if code_url:
            aev("Code released with the paper — openness/execution signal.",
                "High", "corroborated", code_url, "GitHub")
        if cadence:
            aev(f"{cadence} arXiv paper{'s' if cadence != 1 else ''} in the last 12 months "
                "(author-name search; name collisions possible).",
                "Medium", "corroborated", cad_cit or abs_url, "arXiv")
        if cites:
            aev(f"{int(cites)} citations on Semantic Scholar.", "High", "corroborated",
                cites_cit or abs_url, "Semantic Scholar")
        if coauthors:
            aev(f"Small-team paper: {coauthors} author{'s' if coauthors != 1 else ''}.",
                "Medium", "corroborated", coa_cit or abs_url, "arXiv")
        if aff:
            aev(f"Industry affiliation: {aff}.", "Medium", "corroborated",
                aff_cit or abs_url, "arXiv")
        if fo.get("github"):
            aev("Public GitHub profile (repo owner matches author name).", "Medium",
                "corroborated", f"https://github.com/{fo['github']}", "GitHub")
        aev("Commercialization / company status", "Low", "uncorroborated",
            abs_url, "Unknown", unknown=True)
        aev("Current role / location", "Low", "uncorroborated",
            abs_url, "Unknown", unknown=True)

        a_fields = [pa.get("title"), code_url, cites, coauthors, aff, fo.get("github")]
        a_details = {"source": "arXiv"}
        a_links = [{"label": "arXiv", "url": abs_url}]
        if code_url:
            a_links.append({"label": "Code", "url": code_url})
        if fo.get("github"):
            a_links.append({"label": "GitHub", "url": f"https://github.com/{fo['github']}"})
        a_details["links"] = a_links

        # SCORING.md dimensions from paper signals (absence = coverage 0, never a penalty)
        a_dims = [
            dim("Capability", 70 if code_url else 0, 0.4 if code_url else 0.0),
            dim("Skills", 55, 0.25 if code_url else 0.1),
            dim("Trajectory", min(100, 40 + cadence * 10), min(1.0, cadence / 4)),
            dim("Ceiling", min(100, 50 + len(title) // 4), 0.4),
            dim("Intent", 40, 0.15),
            dim("Provenance", 60 if aff else 0, 0.33 if aff else 0.0),
            dim("Traction", min(100, int(cites or 0)), min(1.0, int(cites or 0) / 50)),
        ]
        a_score, a_conf, a_band = aggregate_dims(a_dims)

        out.append({
            "id": f"arxiv_{uid}",
            "name": name,
            "email": f"{uid}@vcbrain.example",
            "location": "Unknown",
            "completeness": round(sum(1 for x in a_fields if x) / len(a_fields) * 100),
            "bio": (f"{name.split()[0]} is a researcher — first-author of \"{title[:120]}\""
                    + (f" ({aff})." if aff else ".") + " Pre-founding, sourced via arXiv."),
            "skills": ["Research", "Machine Learning", "Python"] + (["Open source"] if code_url else []),
            "contact": {"email": f"{uid}@vcbrain.example",
                        **({"website": code_url} if code_url else {})},
            "details": a_details,
            "dimensions": a_dims,
            "projects": [{
                "id": f"arxiv_{uid}_p1",
                "name": project,
                "sector": sector,
                "stage": "Pre-seed",
                "oneLiner": one,
                "description": f"Academic work: {title}. Commercialization status unknown — "
                               "pre-founding signal from the arXiv channel.",
            }],
            "scores": {
                "founder": a_score,
                "founderTrend": "up" if cadence >= 3 else "flat",
                "market": "Neutral",
                "marketTrend": "flat",
                "fit": "Pivot potential",
                "fitTrend": "flat",
                "confidence": a_conf,
                "band": a_band,
            },
            "coldStart": True,
            "evidence": E,
        })

    # most-complete profiles first; founder score breaks ties
    out.sort(key=lambda r: (-(r.get("completeness") or 0), -r["scores"]["founder"]))

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
