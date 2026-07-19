"""Inbound applications — a founder self-submits and the SAME pipeline scores them.

Closes the Apply → Screen → Converge loop (brief MVP #4): an application from the
founder onboarding form becomes a scored candidate in the funnel, tagged
`source_track="inbound"`, flowing through the identical screening → thesis → memo
path as outbound-discovered founders.

If the applicant gives a GitHub handle we score their real public code; otherwise
we score what the form provides (self-reported → thin coverage → wide confidence
band, honestly uncertain), and it can be enriched later. The self-reported fields
are carried as claims (Medium/Low trust), never treated as verified.
"""
from __future__ import annotations

import re

from . import founder_score as fscore
from . import memory
from .founder_score import Component, FounderScore, WEIGHTS, _aggregate, _clamp


def _gh_handle(*vals):
    for v in vals:
        if not v:
            continue
        v = str(v).strip()
        if "github.com/" in v:
            seg = v.split("github.com/", 1)[1].strip("/").split("/")[0].split("?")[0]
            if seg:
                return seg
        elif v and " " not in v and "/" not in v and "." not in v and v.lower() not in ("na", "none"):
            return v
    return None


def _slug(app):
    base = (app.get("company") or app.get("name") or "applicant").strip().lower()
    return "inbound-" + (re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:40] or "applicant")


def _form_text(app):
    return " ".join(str(app.get(k) or "") for k in ("company", "one_liner", "industry", "notes")).lower()[:1000]


_APP_FIELDS = ("company", "one_liner", "website", "location", "industry", "stage", "notes")


def _application(app):
    return {k: app.get(k, "") or "" for k in _APP_FIELDS}


def _form_attributes(app):
    return {
        "location": app.get("location", "") or "",
        "languages": [],
        "profile_text": _form_text(app),
        "inferred_stage": app.get("stage") or "pre-seed/idea",
        "stars": 0, "forks": 0, "followers": 0,
        "source_track": "inbound",
        "application": _application(app),
    }


def _score_from_form(app):
    """Thin, honest score from a self-reported application (no public signal yet)."""
    one = (app.get("one_liner") or app.get("company") or "").strip()
    comm = _clamp(35 + (20 if len(one) > 60 else 8 if one else 0))
    evidence = [f'self-reported pitch: "{one[:90]}"'] if one else []
    components = [Component("Communication", comm, 0.35, evidence, "self-reported — unverified")]
    for c in components:
        c.weight = WEIGHTS.get(c.name, 1.0)
    score, confidence, band = _aggregate(components)
    return FounderScore(
        handle=_slug(app), profile_url=app.get("website", "") or "",
        name=app.get("name") or app.get("company") or "Applicant",
        score=score, confidence=confidence, band=band, components=components,
        capability_detail={"backend": "inbound:self-reported", "dimensions": {}},
        attributes=_form_attributes(app),
    )


def _augment_github(fs, app):
    a = fs.attributes
    a["source_track"] = "inbound"
    a["application"] = _application(app)
    if not a.get("location") and app.get("location"):
        a["location"] = app["location"]
    stated = _form_text(app)          # fold the founder's STATED domain into the text
    if stated:
        a["profile_text"] = (a.get("profile_text", "") + " " + stated).strip()[:1200]
    return fs


def _app_signals(app):
    return [{"signal_type": "application", "payload": _application(app),
             "url": app.get("website", "") or ""}]


def score_application(app, persist=True):
    """Score one inbound application (dict). Returns a FounderScore (source_track=inbound)."""
    gh = _gh_handle(app.get("github"), app.get("website"), app.get("notes"))
    if gh:
        try:
            fs = fscore.score_github_handle(gh, persist=False)
            _augment_github(fs, app)
        except Exception:
            fs = _score_from_form(app)   # handle didn't resolve / API down -> fall back to the form
    else:
        fs = _score_from_form(app)
    if persist:
        memory.persist_native(fs, _app_signals(app))
    return fs
