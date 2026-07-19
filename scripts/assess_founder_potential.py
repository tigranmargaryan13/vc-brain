#!/usr/bin/env python3
"""Founder-potential assessment — the layer on top of the academic channels that
answers: "this person hasn't founded anything — how likely is their research to
become a fundable company?"

Consumes academic_founder_signals.json (run scripts/run_academic_sourcing.py
first) and emits potential_founder_signals.json in the standard channel shape,
so the combiner merges it like any other source.

Per founder:
  applied_research          — LLM-classified (OpenAI): industrial problem vs pure
                              theory, 0..1, with a one-line rationale (T1)
  market_vertical           — LLM-mapped to known commercialization verticals
  builder_breadth           — GitHub *profile* stats (public repos, followers),
                              only for authors with a verified handle
  founder_intent            — bio tells: "building", "stealth", personal site (+only)
  pre_founding_status       — negative-space verification: GitHub bio founder
                              markers + cross-check vs our ProductHunt rosters.
                              "pre-founding" / "founder markers found" / "unknown"
  founder_potential_score   — positive-only additive 0-100 over the above +
                              execution signals already in the merged record

Honesty rules: LLM sees only title/topic we actually collected — no invention;
absence of a checkable profile => status "unknown", never a penalty.

Run: .venv/bin/python scripts/assess_founder_potential.py
"""
import csv
import json
import math
import os
import re
import sys
import time

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(REPO, "academic_founder_signals.json")
OUT = os.path.join(REPO, "potential_founder_signals.json")

VERTICALS = ["enterprise AI", "AI infrastructure", "autonomous systems",
             "cybersecurity", "drug discovery / biotech", "healthcare",
             "fintech", "climate / energy", "robotics", "other"]
HOT_VERTICALS = set(VERTICALS) - {"other"}
FOUNDER_MARKERS = re.compile(r"\b(co-?founder|founder|ceo|cto|founding)\b", re.I)
INTENT_MARKERS = re.compile(r"\b(building|stealth|working on|launching)\b", re.I)

GH_HEADERS = {"Accept": "application/vnd.github.v3+json"}
if os.getenv("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"


def _sig(criterion, description, value, citation, evidence=None, positive_only=False):
    return {"criterion": criterion, "axis": "Founder", "tier": "T1",
            "positive_only": positive_only, "description": description,
            "value": value, "citation": citation, "evidence": evidence}


def sig_value(f, key):
    return (f.get("signals", {}).get(key) or {}).get("value")


def known_shipped_names():
    """Names already shipping products in our other sourcing datasets (ProductHunt)."""
    names = set()
    for fname, getter in [
        ("producthunt_founder_signals.json",
         lambda r: (r.get("founder") or {}).get("name")),
    ]:
        try:
            for r in json.load(open(os.path.join(REPO, fname))):
                n = getter(r)
                if n:
                    names.add(re.sub(r"\s+", " ", n.strip().lower()))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    try:
        for row in csv.DictReader(open(os.path.join(REPO, "founder_product_info.csv"))):
            n = (row.get("name") or "").strip().lower()
            if n:
                names.add(re.sub(r"\s+", " ", n))
    except FileNotFoundError:
        pass
    return names


def github_profile(handle):
    try:
        r = requests.get(f"https://api.github.com/users/{handle}",
                         headers=GH_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException:
        return None


def llm_classify(founders):
    """One batched OpenAI call: applied-ness + vertical per founder, from the
    title/topic we actually collected. Returns {name: {...}} or {} on failure."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("  (OPENAI_API_KEY missing — applied/vertical signals skipped)")
        return {}
    items = [{"name": f["name"],
              "title": (f.get("paper") or {}).get("title") or "",
              "topic": (f.get("paper") or {}).get("topic")
                       or "; ".join((f.get("paper") or {}).get("categories") or [])}
             for f in founders]
    body = {
        "model": "gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "max_tokens": 3000,
        "messages": [
            {"role": "system", "content":
             "You assess commercialization potential of research papers for a VC "
             "sourcing pipeline. For each item, judge ONLY from the given title/"
             "topic — never invent facts. Return JSON {\"assessments\": [{\"name\", "
             "\"applied\" (0..1: 1 = solves a concrete industrial/business problem, "
             "0 = pure theory), \"vertical\" (one of: " + ", ".join(VERTICALS) + "), "
             "\"rationale\" (<=15 words)}]}."},
            {"role": "user", "content": json.dumps(items)},
        ],
    }
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json=body, timeout=120)
        r.raise_for_status()
        data = json.loads(r.json()["choices"][0]["message"]["content"])
        return {a["name"]: a for a in data.get("assessments", []) if a.get("name")}
    except Exception as e:
        print(f"  (LLM classification failed: {e} — signals skipped)")
        return {}


def main():
    try:
        founders = json.load(open(IN))
    except FileNotFoundError:
        print(f"missing {IN} — run scripts/run_academic_sourcing.py first")
        return 1

    shipped = known_shipped_names()
    assessments = llm_classify(founders)
    print(f"LLM assessments: {len(assessments)}/{len(founders)}")

    records = []
    for f in founders:
        name = f["name"]
        norm = re.sub(r"\s+", " ", name.strip().lower())
        signals = {}
        cite_default = ((f.get("paper") or {}).get("url")
                        or "https://github.com/tigranmargaryan13/vc-brain")

        a = assessments.get(name)
        if a:
            signals["applied_research"] = _sig(
                "applied_research",
                f"LLM-classified applied-ness of the research ({a.get('rationale')})",
                round(float(a.get("applied") or 0), 2), cite_default)
            signals["market_vertical"] = _sig(
                "market_vertical",
                "Commercialization vertical the research maps to (LLM-classified)",
                a.get("vertical") or "other", cite_default)

        # GitHub profile: builder breadth + founder/intent markers (verified handles only)
        handle = (f.get("founder_meta") or {}).get("github")
        status, status_ev = "unknown (no verifiable public profile)", None
        if handle:
            prof = github_profile(handle)
            time.sleep(0.5)
            if prof:
                prof_url = prof.get("html_url") or f"https://github.com/{handle}"
                signals["builder_breadth"] = _sig(
                    "builder_breadth",
                    "GitHub profile-level building activity (public repos, followers)",
                    {"public_repos": prof.get("public_repos"),
                     "followers": prof.get("followers")},
                    prof_url)
                bio = " ".join(str(x) for x in
                               [prof.get("bio"), prof.get("company")] if x)
                if INTENT_MARKERS.search(bio) or prof.get("hireable"):
                    signals["founder_intent"] = _sig(
                        "founder_intent",
                        "Bio/profile intent tells (building / stealth / open to work)",
                        True, prof_url, [bio[:120]] if bio else None,
                        positive_only=True)
                if FOUNDER_MARKERS.search(bio):
                    status = "founder markers found in profile"
                    status_ev = [bio[:120]]
                else:
                    status = "pre-founding (no founder markers in profile)"
                    status_ev = [bio[:120]] if bio else None
        if norm in shipped:
            status = "has shipped products (matched ProductHunt roster)"
        signals["pre_founding_status"] = _sig(
            "pre_founding_status",
            "Negative-space check: GitHub bio founder markers + ProductHunt roster "
            "cross-check. 'unknown' stays unknown — never a penalty.",
            status, cite_default, status_ev)

        # ---- founder potential: positive-only additive over assessment +
        #      execution signals already merged into the academic record ----
        p = 0.0
        p += float((signals.get("applied_research") or {}).get("value") or 0) * 22
        if (signals.get("market_vertical") or {}).get("value") in HOT_VERTICALS:
            p += 10
        if sig_value(f, "open_source_release") or (f.get("paper") or {}).get("code_url"):
            p += 10
        days = sig_value(f, "repo_recent_activity")
        if days is not None and int(days) <= 45:
            p += 8
        bb = (signals.get("builder_breadth") or {}).get("value") or {}
        p += min(math.log10((bb.get("followers") or 0) + 1) * 4
                 + min((bb.get("public_repos") or 0), 30) / 10, 12)
        if signals.get("founder_intent"):
            p += 12
        if sig_value(f, "industry_affiliation"):
            p += 8
        p += min(int(sig_value(f, "publication_cadence_12mo") or 0), 8)
        h = sig_value(f, "author_h_index")
        if h is not None:
            p += min(int(h), 8)
        if "shipped" in status:
            p += 6  # they demonstrably execute — but they're not pre-founding
        potential = int(round(min(p, 95)))

        signals["founder_potential_score"] = _sig(
            "founder_potential_score",
            "Positive-only composite: applied research x vertical x execution x "
            "builder behavior x intent. Cold-start rule: unknowns add nothing.",
            potential, cite_default)

        records.append({"channel": "potential_assessment",
                        "founder": {"name": name}, "signals": signals})
        print(f"  {potential:>3}  {name} — {status}")

    with open(OUT, "w") as fh:
        json.dump(records, fh, indent=1, ensure_ascii=False)
    print(f"\nwrote {len(records)} assessments -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
