"""Data-source loaders — turn a discovered dataset into resolver-ready candidates.

Bridges real sourcing datasets (ProductHunt exports, event guest lists) into the
candidate shape the resolver + pipeline consume:
    {name, github, twitter, linkedin, email, website, source}
Handles are extracted from profile URLs so GitHub identities can be scored directly.
"""
from __future__ import annotations

import csv
import os

_ROOT = os.path.dirname(os.path.dirname(__file__))
PRODUCTHUNT_CSV = os.path.join(_ROOT, "producthunt_founder_web_enriched.csv")
LUMA_CSV = os.path.join(_ROOT, "nyc_dinner_guests.csv")


def _handle(value, hosts):
    """Extract a bare handle from a profile URL (or accept an already-bare handle)."""
    if not value:
        return None
    v = value.strip()
    for h in hosts:
        if f"{h}/" in v:
            seg = v.split(f"{h}/", 1)[1].strip("/").split("/")[0].split("?")[0]
            return seg or None
    if v and " " not in v and "/" not in v and "." not in v:
        return v
    return None


def _clean(v):
    v = (v or "").strip()
    return v or None


def from_producthunt_csv(path=PRODUCTHUNT_CSV):
    """ProductHunt web-enriched founders → candidate dicts."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append({
                "name": _clean(row.get("name")),
                "github": _handle(row.get("github"), ["github.com"]),
                "twitter": _handle(row.get("twitter"), ["twitter.com", "x.com"]),
                "linkedin": _clean(row.get("linkedin")),
                "email": _clean(row.get("emails")),
                "website": _clean(row.get("website")),
                "source": "producthunt",
            })
    return out


def from_luma_csv(path=LUMA_CSV):
    """Luma event guest list → candidate dicts (no GitHub column; resolver/enrichment fodder)."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append({
                "name": _clean(row.get("guest")) or _clean(row.get("first_name")),
                "github": None,
                "twitter": _handle(row.get("twitter"), ["twitter.com", "x.com"]),
                "linkedin": _clean(row.get("linkedin")),
                "email": _clean(row.get("email")),
                "website": _clean(row.get("website")),
                "source": "luma_event",
            })
    return out
