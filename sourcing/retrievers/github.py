"""GitHub retriever — user profiles and repositories.

GITHUB_TOKEN is optional but recommended: it raises the rate limit from 60 to
5000 requests/hour. Create one at https://github.com/settings/tokens (no scopes
needed for public data).

The `resolve_user` helper verifies a candidate handle really belongs to a
person (type == User and the display name overlaps) so you don't attach the
wrong account's repos — useful when matching a name/handle from another source.

Run:  python retrievers/github.py octocat
"""

import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

API = "https://api.github.com"
_session = requests.Session()


def _headers():
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h


def _get(path, params=None):
    for _ in range(3):
        r = _session.get(f"{API}{path}", headers=_headers(), params=params, timeout=20)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = int(r.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset - time.time(), 0)
            if wait > 60:
                raise RuntimeError("GitHub rate limit hit; set GITHUB_TOKEN to raise it")
            time.sleep(wait + 1)
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def get_profile(username):
    """Full user profile: name, company, location, bio, blog, followers, etc."""
    return _get(f"/users/{username}")


def get_repos(username, sort="pushed", per_page=100):
    """First page of a user's public repos (up to per_page)."""
    return _get(f"/users/{username}/repos",
                {"type": "owner", "sort": sort, "per_page": per_page}) or []


def _tokens(name):
    return {t for t in re.split(r"\W+", (name or "").lower()) if len(t) >= 3}


def resolve_user(name, candidates):
    """Return the profile of the first candidate handle that is a real personal
    account (type == User) whose display name overlaps `name`."""
    want, seen = _tokens(name), set()
    for cand in candidates:
        cand = (cand or "").strip().lstrip("@")
        if not cand or "/" in cand or cand.lower() in seen:
            continue
        seen.add(cand.lower())
        prof = get_profile(cand)
        if prof and prof.get("type") == "User" and want & _tokens(prof.get("name")):
            return prof
    return None


def summarize(username):
    """Compact profile + repo signals for one user."""
    prof = get_profile(username)
    if not prof:
        return None
    repos = get_repos(username)
    originals = [r for r in repos if not r["fork"]]
    return {
        "username": prof["login"], "name": prof.get("name"),
        "company": prof.get("company"), "location": prof.get("location"),
        "bio": prof.get("bio"), "blog": prof.get("blog") or None,
        "twitter": prof.get("twitter_username"),
        "followers": prof.get("followers"), "public_repos": prof.get("public_repos"),
        "total_stars": sum(r["stargazers_count"] for r in originals),
        "languages": sorted({r["language"] for r in originals if r["language"]}),
        "top_repos": [{"name": r["name"], "stars": r["stargazers_count"],
                       "url": r["html_url"], "description": r.get("description")}
                      for r in sorted(originals, key=lambda x: -x["stargazers_count"])[:5]],
    }


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "octocat"
    info = summarize(user)
    if not info:
        raise SystemExit(f"user '{user}' not found")
    print(f"{info['name']} (@{info['username']})")
    print(f"  {info['location'] or '?'} | {info['company'] or '?'} | "
          f"{info['followers']} followers | {info['public_repos']} repos | "
          f"{info['total_stars']} stars")
    print(f"  languages: {', '.join(info['languages'][:8])}")
    for r in info["top_repos"]:
        print(f"    {r['stars']:>5}  {r['name']} — {r['url']}")
