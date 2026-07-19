"""FastAPI backend — serves the real scored founders to the React UI.

Bridges sourcing/export.py (deduped funnel + memos) into the exact FounderProfile
shape frontend/src/lib/api.ts expects, so the UI renders real pipeline output
instead of mock-data.ts. Scope: founder data only (searchFounders / getFounder /
generateMemo). Auth, companies, notifications stay client-side in the app.

Run from repo root:  uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sourcing.export import build_dataset

app = FastAPI(title="VC Brain API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# --- vocab maps: our export terms -> the frontend's enums ---
_TREND = {"improving": "up", "declining": "down", "stable": "flat", "new": "flat"}
_MARKET = {"bullish": "Bullish", "neutral": "Neutral", "bear": "Bear"}
_FIT = {"survives": "Survives as-is", "pivot-capable": "Pivot potential",
        "market-carried": "Pivot potential", "weak": "At risk"}
_VERDICT = {"ADVANCE": "Strong yes", "REVIEW": "Conditional yes", "PASS": "Pass"}
_TRUST = {"High": "High", "Med": "Medium", "Low": "Low"}

_cache = {"data": None}


def _dataset():
    if _cache["data"] is None:
        _cache["data"] = build_dataset()
    return _cache["data"]


def _label(url):
    m = re.search(r"https?://([^/]+)", url or "")
    return m.group(1).replace("www.", "") if m else ("internal" if not url else "source")


def _claim(c):
    state = ("corroborated" if c.get("verified") is True
             else "contradicted" if c.get("contradicts") else "uncorroborated")
    return {"text": c["text"], "trust": _TRUST.get(c.get("trust_label"), "Low"),
            "state": state, "sourceUrl": c.get("source") or "", "sourceLabel": _label(c.get("source"))}


def _scores(fv):
    s = fv["screen"]
    return {
        "founder": round(fv["founder_score"]["value"]),
        "founderTrend": _TREND.get(s["founder"]["trend"], "flat"),
        "market": _MARKET.get(s["market"]["stance"], "Neutral"),
        "marketTrend": _TREND.get(s["market"]["trend"], "flat"),
        "fit": _FIT.get(s["idea_vs_market"]["stance"], "Pivot potential"),
        "fitTrend": _TREND.get(s["idea_vs_market"]["trend"], "flat"),
    }


def _section(sec):
    out = {"id": re.sub(r"[^a-z0-9]+", "-", sec["title"].lower()).strip("-"), "title": sec["title"]}
    if sec["title"] == "SWOT":
        swot = {"S": [], "W": [], "O": [], "T": []}
        for c in sec["claims"]:
            cl, low = _claim(c), c["text"].lower()
            bucket = "S" if low.startswith("strength") else "W" if low.startswith("weakness") \
                else "O" if low.startswith("opportunity") else "T"
            swot[bucket].append(cl)
        out["swot"] = swot
    else:
        out["bullets"] = [_claim(c) for c in sec["claims"]]
    if sec.get("gaps"):
        out["gaps"] = sec["gaps"]
    return out


def _memo(fv):
    sections = [_section(s) for s in fv["memo"]["sections"]]
    top = [c["text"] for s in fv["memo"]["sections"]
           if s["title"] == "Investment hypotheses" for c in s["claims"]][:4]
    return {"verdict": _VERDICT.get(fv["thesis_fit"]["verdict"], "Pass"),
            "scoresRestated": _scores(fv),
            "topReasons": top or fv["thesis_fit"]["matched"][:3],
            "sections": sections}


def _snapshot_bits(fv):
    location, product, one_liner = "", "", ""
    for s in fv["memo"]["sections"]:
        if s["title"] == "Company snapshot":
            for c in s["claims"]:
                t = c["text"]
                if t.startswith("Based in "):
                    location = t[len("Based in "):].rstrip(".")
                m = re.search(r"\(([^)]+)\)", t)
                if m and "/" in m.group(1) and not product:   # a repo path, not "launch(es)"/"(inferred)"
                    product = m.group(1)
        elif s["title"] == "Problem & product":
            for c in s["claims"]:
                m = re.search(r'"(.+)"', c["text"])
                if m:
                    one_liner = m.group(1)
    return location, product, one_liner


def _profile(fv):
    location, product, one_liner = _snapshot_bits(fv)
    project = {"id": fv["handle"] + "::p1", "name": product or fv["sector"].title(),
               "sector": fv["sector"], "stage": fv["categories"]["stage"],
               "oneLiner": one_liner or fv["screen"]["idea_vs_market"]["rationale"]}
    evidence = []
    for s in fv["memo"]["sections"]:
        evidence += [_claim(c) for c in s["claims"]]
        evidence += [{"text": g, "trust": "Low", "state": "uncorroborated",
                      "sourceUrl": "", "sourceLabel": "gap", "unknown": True} for g in s.get("gaps", [])]
    return {
        "id": fv["handle"], "name": fv["name"], "email": "",
        "location": location, "projects": [project], "scores": _scores(fv),
        "coldStart": "cold-start" in fv.get("tags", []),
        "hasContradiction": bool(fv["memo"]["contradictions"]),
        "evidence": evidence, "memoFor": {project["id"]: _memo(fv)},
    }


@app.get("/health")
def health():
    return {"ok": True, "founders": len(_dataset()["founders"])}


@app.get("/api/founders")
def founders(q: str = "", limit: int = 100):
    fvs = _dataset()["founders"]
    if q:
        ql = q.lower()
        fvs = [f for f in fvs if ql in f["name"].lower() or ql in f["sector"].lower()
               or any(ql in t for t in f.get("tags", []))]
    return [_profile(f) for f in fvs[:limit]]


@app.get("/api/founders/{fid}")
def founder(fid: str):
    for f in _dataset()["founders"]:
        if f["handle"] == fid:
            return _profile(f)
    raise HTTPException(status_code=404, detail="founder not found")


@app.get("/api/thesis")
def thesis():
    return _dataset()["thesis"]


@app.post("/api/refresh")
def refresh():
    _cache["data"] = None
    return {"refreshed": True, "founders": len(_dataset()["founders"])}
