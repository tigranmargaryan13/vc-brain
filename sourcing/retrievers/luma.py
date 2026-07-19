"""Luma events retriever — city events (e.g. dinners) with guests and hosts.

No API key required. Luma's official Public API only manages *your own*
calendar, so for city-wide discovery we use the same public endpoint the
luma.com website itself calls:

    GET https://api.lu.ma/discover/get-paginated-events

It accepts a geographic bounding box (north/south/east/west) and returns every
public upcoming event in that area, paginated via `pagination_cursor`.

Guest and host data is read from each event page's embedded JSON. Only the
publicly shown roster is available (hosts + `featured_guests`, capped at ~10 by
Luma, and only when the host enabled "show guest list"). Emails/full lists are
NOT public — they require host login and are not collected here.

Run:  python retrievers/luma.py
"""

import csv
import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

DISCOVER_URL = "https://api.lu.ma/discover/get-paginated-events"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; sourcing/1.0)"}
NEXT_DATA_RE = re.compile(r'__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)

# Bounding box covering the five boroughs of New York City.
NYC_BBOX = {"north": 40.92, "south": 40.49, "west": -74.26, "east": -73.70}
DINNER_KEYWORDS = ("dinner", "supper", "tasting menu", "omakase", "chef's table")


# --------------------------------------------------------------- discovery
def fetch_events(bbox=NYC_BBOX, extra_params=None, max_pages=100, delay=0.15):
    """Paginate the Luma discovery feed for a bounding box; return event dicts."""
    events, cursor = [], None
    for _ in range(max_pages):
        params = {"pagination_limit": 50, **bbox, **(extra_params or {})}
        if cursor:
            params["pagination_cursor"] = cursor
        resp = requests.get(DISCOVER_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        events.extend(e["event"] for e in data["entries"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
        time.sleep(delay)
    return events


def filter_events(events, keywords=DINNER_KEYWORDS):
    """Keep events whose name contains any of the keywords."""
    return [e for e in events if any(k in e["name"].lower() for k in keywords)]


# ------------------------------------------------------------- event detail
def fetch_event_detail(slug):
    """Return the embedded event-detail JSON from a public Luma event page."""
    resp = requests.get(f"https://luma.com/{slug}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    match = NEXT_DATA_RE.search(resp.text)
    return json.loads(match.group(1))["props"]["pageProps"]["initialData"]["data"]


def _social(kind, handle):
    if not handle:
        return None
    h = str(handle).strip().lstrip("@")
    return {
        "instagram": f"https://instagram.com/{h}",
        "twitter": f"https://x.com/{h}",
        "linkedin": "https://www.linkedin.com" + (h if h.startswith("/") else "/in/" + h),
        "tiktok": f"https://tiktok.com/@{h}",
        "youtube": f"https://youtube.com/@{h}",
    }.get(kind, h)


def person_record(p, event, role):
    """Every public field for one guest/host of an event."""
    return {
        "event": event["name"],
        "event_url": f"https://luma.com/{event['url']}",
        "role": role,
        "name": p.get("name"),
        "username": p.get("username"),
        "bio": p.get("bio_short"),
        "verified": p.get("is_verified"),
        "linkedin": _social("linkedin", p.get("linkedin_handle")),
        "twitter": _social("twitter", p.get("twitter_handle")),
        "instagram": _social("instagram", p.get("instagram_handle")),
        "website": p.get("website"),
        "avatar_url": p.get("avatar_url"),
        "luma_profile": f"https://luma.com/user/{p['api_id']}" if p.get("api_id") else None,
        "api_id": p.get("api_id"),
    }


def collect_guests(events, delay=0.3):
    """For each event, fetch its hosts + publicly shown guests."""
    people = []
    for e in events:
        try:
            detail = fetch_event_detail(e["url"])
        except Exception as err:  # noqa: BLE001
            print(f"  skip {e['url']}: {err}")
            continue
        for host in (detail.get("hosts") or []):
            people.append(person_record(host, e, "host"))
        for guest in (detail.get("featured_guests") or []):
            people.append(person_record(guest, e, "guest"))
        e["_guest_count"] = detail.get("guest_count") or 0
        time.sleep(delay)
    return people


# ----------------------------------------------------------------------- CLI
if __name__ == "__main__":
    print("Fetching all NYC events...")
    all_events = fetch_events()
    dinners = filter_events(all_events)
    print(f"  {len(all_events)} events -> {len(dinners)} dinners")

    with open(config.data_path("nyc_dinners.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "start", "city", "address", "url"])
        w.writeheader()
        for e in dinners:
            geo = e.get("geo_address_info") or {}
            w.writerow({"name": e["name"], "start": e["start_at"],
                        "city": geo.get("city_state"), "address": geo.get("full_address"),
                        "url": f"https://luma.com/{e['url']}"})

    print("Fetching guests + hosts...")
    people = collect_guests(dinners)
    cols = ["event", "role", "name", "username", "bio", "verified", "linkedin",
            "twitter", "instagram", "website", "luma_profile", "api_id", "event_url"]
    with open(config.data_path("nyc_dinner_guests.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(people)

    hosts = sum(p["role"] == "host" for p in people)
    print(f"  {len(people)} people ({hosts} hosts, {len(people)-hosts} guests)")
    print("  -> data/nyc_dinners.csv, data/nyc_dinner_guests.csv")
