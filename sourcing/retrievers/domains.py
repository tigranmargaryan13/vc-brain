"""Domain registration lookup via RDAP — a "fresh domain" intent signal.

No API key required. RDAP is the successor to WHOIS and returns structured JSON.
A recently registered domain often means a brand-new venture / waitlist page.

Product Hunt's `website` field is a producthunt.com/r/<id> tracking redirect, so
`real_domain` follows it to the actual product host before the lookup.

Run:  python retrievers/domains.py stripe.com
"""

import datetime
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_session = requests.Session()
_cache = {}


def _host(url):
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0].split("?")[0].split(":")[0].lower()


def real_domain(url):
    """Resolve the real host, following a Product Hunt /r/ redirect if needed."""
    if not url:
        return None
    if url in _cache:
        return _cache[url]
    host = _host(url)
    if host.endswith("producthunt.com"):
        try:
            r = _session.get(url, headers={"User-Agent": "sourcing/1.0"},
                             timeout=15, allow_redirects=True)
            host = _host(r.url)
        except requests.RequestException:
            host = None
    result = host if host and "." in host and not host.endswith("producthunt.com") else None
    _cache[url] = result
    return result


def registration_date(url):
    """Return the domain's registration datetime (UTC), or None."""
    host = real_domain(url)
    if not host:
        return None
    try:
        r = _session.get(f"https://rdap.org/domain/{host}", timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return None
        events = {e["eventAction"]: e["eventDate"] for e in r.json().get("events", [])}
        reg = events.get("registration")
        return datetime.datetime.fromisoformat(reg.replace("Z", "+00:00")) if reg else None
    except (requests.RequestException, ValueError, KeyError):
        return None


def age_days(url, today=None):
    """Days since the domain was registered (None if unknown)."""
    reg = registration_date(url)
    if not reg:
        return None
    today = today or datetime.datetime.now(datetime.timezone.utc)
    return (today - reg).days


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "producthunt.com"
    days = age_days(target)
    host = real_domain(target)
    if days is None:
        print(f"{host or target}: registration date unavailable")
    else:
        fresh = " (FRESH < 180d)" if days <= 180 else ""
        print(f"{host}: {days} days old ({days/365:.1f} years){fresh}")
