"""Personal-site enricher — bio, contact email, and social links.

No API key required. Fetches only pages a person chose to publish (e.g. the
website they linked from a Product Hunt or Luma profile) and reads the bio /
contact email / social links they put there themselves. This is the compliant
way to reach someone's other socials (including LinkedIn/Twitter URLs) — they
published them; we never touch a gated platform. Absent fields are None.

Run:  python retrievers/websites.py https://example.com
"""

import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; sourcing-enricher/1.0)"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
EMAIL_JUNK = ("example.com", "domain.com", "email.com", "sentry", "wixpress", "@2x",
              "@3x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", "yourname",
              "your@", "name@", "user@", "you@", "test@", "@example", "@school.edu")
SOCIALS = {
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/[\w\-%.]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share|home|hashtag)[A-Za-z0-9_]{2,15}", re.I),
    "github": re.compile(r"https?://(?:www\.)?github\.com/(?!features|topics|about|orgs|sponsors|apps|login)[A-Za-z0-9\-]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/)[\w\-]+", re.I),
}
DESC_RES = [re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', re.I),
            re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', re.I),
            re.compile(r"<title[^>]*>([^<]+)</title>", re.I)]
# messaging/social links are not personal sites — skip fetching them
SKIP_HOSTS = ("chat.whatsapp.com", "wa.me", "t.me", "discord.gg", "instagram.com",
              "twitter.com", "x.com", "linkedin.com", "facebook.com", "linktr.ee")


def _emails(html):
    out = []
    for e in re.findall(r"mailto:([^\"'?>\s]+)", html, re.I) + EMAIL_RE.findall(html):
        el = re.sub(r"[^a-z0-9]+$", "", re.sub(r"^[^a-z0-9]+", "", e.strip().lower()))
        if "@" in el and "." in el.split("@")[-1] and not any(j in el for j in EMAIL_JUNK):
            if el not in out:
                out.append(el)
    return out


def _bio(html):
    for pattern in DESC_RES:
        m = pattern.search(html)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()[:300]
    return None


def enrich(url, timeout=15):
    """Fetch one site; return bio, emails, and social links. Never raises."""
    result = {"url": url, "ok": False, "status": None, "resolved_url": None,
              "bio": None, "emails": [], "linkedin": None, "twitter": None,
              "github": None, "instagram": None, "youtube": None}
    if not url or not url.startswith("http"):
        result["status"] = "skipped"
        return result
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    if host in SKIP_HOSTS:
        result["status"] = "not-a-personal-site"
        return result
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        result["status"], result["resolved_url"] = r.status_code, r.url
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            return result
        html = r.text
        result["ok"] = True
        result["bio"] = _bio(html)
        result["emails"] = _emails(html)
        for name, pattern in SOCIALS.items():
            m = pattern.search(html)
            if m:
                result[name] = m.group(0)
    except requests.RequestException as err:
        result["status"] = f"error: {type(err).__name__}"
    return result


def enrich_many(urls, delay=0.5):
    out = []
    for u in urls:
        out.append(enrich(u))
        time.sleep(delay)
    return out


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://benlang.me"
    info = enrich(target)
    print(f"{info['resolved_url'] or target} -> {info['status']}")
    for k in ("bio", "emails", "linkedin", "twitter", "github"):
        if info[k]:
            print(f"  {k}: {info[k]}")
