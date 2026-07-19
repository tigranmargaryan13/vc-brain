#!/usr/bin/env python3
"""Transform producthunt_founder_signals.json (+ web-enriched CSV) into the
Lovable UI's FounderProfile[] shape (src/lib/mock-data.ts types), emitting a
ready-to-paste src/lib/sourced-founders.ts."""
import csv, json, math, os, re, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(tempfile.gettempdir(), "sourced-founders.ts")

SECTOR_MAP = [
    (["artificial intelligence", "ai", "machine learning", "bots", "gpt", "llm"], "AI/ML"),
    (["developer tools", "software engineering", "github", "api", "open source", "web3"], "Dev Tools"),
    (["fintech", "finance", "payments", "crypto", "investing", "money"], "Fintech"),
    (["health", "fitness", "medical", "wellness"], "Healthtech"),
    (["security", "privacy"], "Cybersecurity"),
    (["climate", "energy", "sustainability"], "Climate"),
    (["hardware", "robotics", "space", "iot"], "Deep Tech"),
    (["biotech"], "Biotech"),
    (["e-commerce", "social", "education", "travel", "food", "lifestyle", "games", "consumer", "dating", "music"], "Consumer"),
    (["saas", "productivity", "marketing", "sales", "no-code", "design tools", "analytics", "work"], "SaaS"),
]

def map_sector(topics):
    for t in topics or []:
        tl = t.lower()
        for keys, sector in SECTOR_MAP:
            if any(k in tl for k in keys):
                return sector
    return "SaaS"

def sval(sig, key):
    s = sig.get(key) or {}
    return s.get("value"), s.get("citation"), s.get("evidence")

def load_pipeline_scores(links):
    """Real pipeline scores from data/founder_scores.jsonl, keyed by PH username.
    Excludes the benln->atom misresolution (Atom org != Ben Lang)."""
    by_entity = {}
    try:
        with open(f"{REPO}/data/founder_scores.jsonl") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    by_entity[r["entity"]] = r  # last run wins
                except Exception:
                    pass
    except FileNotFoundError:
        return {}
    out = {}
    for u, row in links.items():
        gh = (row.get("github") or "").strip().rstrip("/")
        handle = gh.split("github.com/", 1)[1].split("/")[0] if "github.com/" in gh else None
        if not handle or handle == "atom":
            continue
        rec = by_entity.get(handle)
        if rec:
            out[u] = rec
    return out


def main():
    with open(f"{REPO}/producthunt_founder_signals.json") as f:
        rows = json.load(f)
    links = {}
    try:
        with open(f"{REPO}/producthunt_founder_web_enriched.csv", newline="") as f:
            for r in csv.DictReader(f):
                u = (r.get("username") or "").strip()
                if u:
                    links[u] = r
    except FileNotFoundError:
        pass
    pipeline_scores = load_pipeline_scores(links)
    flat = {}
    try:
        with open(f"{REPO}/producthunt_founder_signals.csv", newline="") as f:
            for r in csv.DictReader(f):
                u = (r.get("username") or "").strip()
                if u and u not in flat:
                    flat[u] = r
    except FileNotFoundError:
        pass

    out, seen = [], set()
    for rec in rows:
        fo, la, sig = rec["founder"], rec.get("launch") or {}, rec.get("signals") or {}
        username = (fo.get("username") or "").strip()
        if not username or username in seen:
            continue
        seen.add(username)
        name = (fo.get("name") or "").strip()
        if not name or "redacted" in name.lower():
            name = username
        ph = fo.get("ph_profile") or f"https://www.producthunt.com/@{username}"
        product = (la.get("product") or "").strip() or f"{name}'s project"
        prod_url = la.get("url") or ph

        prior, prior_cit, prior_ev = sval(sig, "prior_building_history")
        serial, _, _ = sval(sig, "serial_founder")
        cadence, cad_cit, _ = sval(sig, "shipping_cadence_12mo")
        career, ea_cit, _ = sval(sig, "earned_attention_career")
        current, _, _ = sval(sig, "earned_attention_current")
        cof, cof_cit, _ = sval(sig, "co_founder_present")
        meng, meng_cit, _ = sval(sig, "market_engagement")
        tenure, _, _ = sval(sig, "building_tenure_days")
        domains, dom_cit, _ = sval(sig, "domain_focus")
        comm, _, _ = sval(sig, "communication_text")

        prior = int(prior or 0); cadence = int(cadence or 0)
        career = int(career or 0); current = int(current or 0)
        tenure = int(tenure or 0)
        comments = int((meng or {}).get("comments") or 0)

        tagline = ""
        if isinstance(comm, str):
            try:
                tagline = (json.loads(comm).get("tagline") or "").strip()
            except Exception:
                pass
        one_liner = tagline or (fo.get("headline") or "").strip() or f"Launched {product} on Product Hunt."
        if len(one_liner) > 110:
            one_liner = one_liner[:107].rstrip() + "…"

        score = 35
        score += min(prior * 5, 15)
        score += 8 if serial else 0
        score += min(cadence * 4, 12)
        score += min(int(math.log10(career + 1) * 5), 12)
        score += min(current // 150, 6)
        score += 4 if cof else 0
        score += min(comments // 30, 5)
        score += min((tenure // 365) * 2, 6)
        score = max(35, min(score, 95))
        pipe = pipeline_scores.get(username)
        if pipe:
            score = max(35, min(round(pipe["score"]), 95))
        cold = career < 100 and prior <= 1 and not pipe

        E = []
        def ev(text, trust, state, url, label, unknown=False):
            item = {"text": text, "trust": trust, "state": state,
                    "sourceUrl": url or ph, "sourceLabel": label}
            if unknown:
                item["unknown"] = True
            E.append(item)

        if prior > 0:
            names = f" ({', '.join((prior_ev or [])[:3])})" if prior_ev else ""
            ev(f"Shipped {prior} product{'s' if prior != 1 else ''} on Product Hunt{names}.",
               "High", "corroborated", prior_cit, "Product Hunt")
        if cadence > 0:
            ev(f"{cadence} launch{'es' if cadence != 1 else ''} in the last 12 months.",
               "High", "corroborated", cad_cit, "Product Hunt")
        if career > 0:
            ev(f"{career} organic upvotes earned across launches (latest: {current}).",
               "High", "corroborated", ea_cit, "Product Hunt")
        if cof:
            ev("Co-founder / co-maker present on launches.", "Medium", "corroborated", cof_cit, "Product Hunt")
        if comments > 0:
            ev(f"{comments} community comments engaged on launches.", "Medium", "corroborated", meng_cit, "Product Hunt")
        if domains:
            ev(f"Domain focus: {', '.join(domains[:3])}.", "Medium", "corroborated", dom_cit, "Product Hunt")
        frow = flat.get(username) or {}
        try:
            team_size = int(frow.get("team_size") or 0)
        except ValueError:
            team_size = 0
        if team_size > 1:
            ev(f"Team of {team_size} on recent launches.", "Medium", "corroborated", ph, "Product Hunt")
        site = (frow.get("website") or "").strip()
        if site.startswith("http"):
            ev("Live product website.", "Medium", "corroborated", site, "Website")
        link = links.get(username) or {}
        gh = (link.get("github") or "").strip()
        li = (link.get("linkedin") or "").strip()
        if pipe:
            band = pipe.get("band") or []
            band_s = f" (90% band {band[0]:.0f}–{band[1]:.0f})" if len(band) == 2 else ""
            ev(f"VC Brain pipeline read their GitHub code: capability score {pipe['score']:.1f}{band_s}.",
               "High", "corroborated", pipe.get("profile_url") or gh, "VC Brain pipeline")
        elif gh and "github.com/" in gh and not gh.endswith("github.com/atom"):
            ev("Public GitHub profile.", "Medium", "corroborated", gh, "GitHub")
        if li and "linkedin.com" in li:
            ev("Public LinkedIn profile.", "Medium", "corroborated", li, "LinkedIn")
        ev("Location / professional background", "Low", "uncorroborated", ph, "Unknown", unknown=True)
        ev("Revenue / traction beyond Product Hunt", "Low", "uncorroborated", ph, "Unknown", unknown=True)

        uid = re.sub(r"[^a-z0-9_]+", "_", username.lower())
        out.append({
            "id": f"ph_{uid}",
            "name": name,
            "email": f"{uid}@ph.example",
            "location": "Unknown",
            "projects": [{
                "id": f"ph_{uid}_p1",
                "name": product,
                "sector": map_sector(domains),
                "stage": "Unknown",
                "oneLiner": one_liner,
            }],
            "scores": {
                "founder": score,
                "founderTrend": "up" if cadence >= 2 else "flat",
                "market": "Neutral",
                "marketTrend": "flat",
                "fit": "Pivot potential",
                "fitTrend": "flat",
            },
            **({"coldStart": True} if cold else {}),
            "evidence": E,
        })

    # ---- NYC founders dinner (Luma) — event-sourcing channel, cold-start ----
    try:
        with open(f"{REPO}/nyc_dinner_guests.csv", newline="") as f:
            guests = list(csv.DictReader(f))
    except FileNotFoundError:
        guests = []
    added = 0
    for g in guests:
        if added >= 10:
            break
        name = (g.get("guest") or "").strip()
        bio = (g.get("bio") or "").strip()
        li = (g.get("linkedin") or "").strip()
        if g.get("role") != "guest" or len(bio) < 20 or not li or " " not in name:
            continue
        uid = re.sub(r"[^a-z0-9_]+", "_", (g.get("username") or name).lower()).strip("_")
        fid = f"luma_{uid}"
        if any(r["id"] == fid for r in out):
            continue
        luma_url = (g.get("event_url") or g.get("luma_profile") or "https://lu.ma").strip()
        bio = re.sub(r"\s+", " ", bio)
        one = bio if len(bio) <= 110 else bio[:107].rstrip() + "…"
        E2 = [
            {"text": "Attended a curated NYC founders dinner (invite-based).", "trust": "Medium",
             "state": "corroborated", "sourceUrl": luma_url, "sourceLabel": "Luma"},
            {"text": f"Public bio: {one}", "trust": "Medium", "state": "uncorroborated",
             "sourceUrl": (g.get("luma_profile") or luma_url), "sourceLabel": "Luma profile"},
            {"text": "Public LinkedIn profile.", "trust": "Medium", "state": "corroborated",
             "sourceUrl": li, "sourceLabel": "LinkedIn"},
            {"text": "Shipped products / building history", "trust": "Low", "state": "uncorroborated",
             "sourceUrl": luma_url, "sourceLabel": "Unknown", "unknown": True},
            {"text": "Current venture details", "trust": "Low", "state": "uncorroborated",
             "sourceUrl": luma_url, "sourceLabel": "Unknown", "unknown": True},
        ]
        out.append({
            "id": fid,
            "name": name,
            "email": f"{uid}@luma.example",
            "location": "New York",
            "projects": [{
                "id": f"{fid}_p1",
                "name": "Undisclosed venture",
                "sector": "Unknown",
                "stage": "Unknown",
                "oneLiner": one,
            }],
            "scores": {
                "founder": 42,
                "founderTrend": "flat",
                "market": "Neutral",
                "marketTrend": "flat",
                "fit": "Pivot potential",
                "fitTrend": "flat",
            },
            "coldStart": True,
            "evidence": E2,
        })
        added += 1

    body = json.dumps(out, indent=2, ensure_ascii=False)
    ts = (
        "// Real founders sourced by the VC Brain pipeline from Product Hunt\n"
        "// (producthunt_founder_signals.json). Generated offline — do not hand-edit;\n"
        "// regenerate from the sourcing pipeline instead. Scores are cold-start\n"
        "// positive-only heuristics; market/fit axes default to Neutral/Pivot\n"
        "// potential until the analysis pipeline runs. Emails are synthetic.\n"
        "import type { FounderProfile } from \"./mock-data\";\n\n"
        f"export const SOURCED_FOUNDERS: FounderProfile[] = {body};\n"
    )
    with open(OUT, "w") as f:
        f.write(ts)
    with open(f"{REPO}/data/ui/sourced_founders.json", "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    counts = {}
    for r in out:
        counts[r["projects"][0]["sector"]] = counts.get(r["projects"][0]["sector"], 0) + 1
    print(f"founders: {len(out)}  cold-start: {sum(1 for r in out if r.get('coldStart'))}")
    print("sectors:", counts)
    print(f"scores: min {min(r['scores']['founder'] for r in out)}, max {max(r['scores']['founder'] for r in out)}")
    print(f"TS size: {len(ts)} chars")

if __name__ == "__main__":
    main()
