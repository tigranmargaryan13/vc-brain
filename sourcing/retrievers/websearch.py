"""Web search retriever — discover public profile URLs for a person.

This is the COMPLIANT bridge to LinkedIn / Twitter / GitHub data: a web search
returns public result URLs (discovery), which is fine. It does NOT fetch the
gated page content behind those URLs — that would be scraping. Use the URL a
search returns, then let the person decide to share more.

Pluggable — set ONE provider key in .env and this module auto-detects it:

  Provider        Env var(s)               Free tier            Notes
  --------        ----------               ---------            -----
  Tavily          TAVILY_API_KEY           1000 searches/mo     JSON, built for LLM apps
  SerpAPI         SERPAPI_API_KEY          100 searches/mo      real Google results
  Brave Search    BRAVE_API_KEY            2000 queries/mo      independent index
  Google CSE      GOOGLE_CSE_API_KEY +     100 queries/day      official, needs an
                  GOOGLE_CSE_CX                                 engine id (cx)

Run:  python retrievers/websearch.py "Jane Doe founder"
"""

import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_session = requests.Session()

PROFILE_HOSTS = {
    "linkedin": re.compile(r"https?://[a-z.]*linkedin\.com/(?:in|company)/[\w\-%.]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]{2,15}\b", re.I),
    "github": re.compile(r"https?://(?:www\.)?github\.com/[A-Za-z0-9\-]+/?$", re.I),
    "crunchbase": re.compile(r"https?://(?:www\.)?crunchbase\.com/(?:person|organization)/[\w\-]+", re.I),
}


def active_provider():
    if config.TAVILY_API_KEY:
        return "tavily"
    if config.SERPAPI_API_KEY:
        return "serpapi"
    if config.BRAVE_API_KEY:
        return "brave"
    if config.GOOGLE_CSE_API_KEY and config.GOOGLE_CSE_CX:
        return "google_cse"
    return None


def search(query, num=10):
    """Return [{title, url, snippet}] from whichever provider is configured."""
    provider = active_provider()
    if not provider:
        raise RuntimeError(
            "No web-search key set. Add one of TAVILY_API_KEY / SERPAPI_API_KEY / "
            "BRAVE_API_KEY / (GOOGLE_CSE_API_KEY + GOOGLE_CSE_CX) to your .env.")
    return globals()[f"_{provider}"](query, num)


def _tavily(query, num):
    r = _session.post("https://api.tavily.com/search", timeout=30, json={
        "api_key": config.TAVILY_API_KEY, "query": query, "max_results": num})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content")}
            for x in r.json().get("results", [])]


def _serpapi(query, num):
    r = _session.get("https://serpapi.com/search", timeout=30, params={
        "engine": "google", "q": query, "num": num, "api_key": config.SERPAPI_API_KEY})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("link"), "snippet": x.get("snippet")}
            for x in r.json().get("organic_results", [])]


def _brave(query, num):
    r = _session.get("https://api.search.brave.com/res/v1/web/search", timeout=30,
                     headers={"X-Subscription-Token": config.BRAVE_API_KEY,
                              "Accept": "application/json"},
                     params={"q": query, "count": num})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("description")}
            for x in r.json().get("web", {}).get("results", [])]


def _google_cse(query, num):
    r = _session.get("https://www.googleapis.com/customsearch/v1", timeout=30, params={
        "key": config.GOOGLE_CSE_API_KEY, "cx": config.GOOGLE_CSE_CX,
        "q": query, "num": min(num, 10)})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("link"), "snippet": x.get("snippet")}
            for x in r.json().get("items", [])]


def find_profiles(name, context="founder", platforms=("linkedin", "twitter", "github")):
    """Discover a person's public profile URLs via search.

    Runs one targeted query per platform and returns {platform: url} for the
    first result whose URL matches that platform's profile pattern. Returns only
    what search surfaces — verify before trusting a match (common names collide).
    """
    found = {}
    for platform in platforms:
        site = {"linkedin": "linkedin.com/in", "twitter": "x.com",
                "github": "github.com"}.get(platform, platform)
        try:
            results = search(f"{name} {context} {site}", num=5)
        except RuntimeError:
            raise
        for res in results:
            m = PROFILE_HOSTS[platform].search(res["url"] or "")
            if m:
                found[platform] = m.group(0)
                break
    return found


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "Paul Graham founder"
    provider = active_provider()
    if not provider:
        raise SystemExit(
            "\nNo web-search provider configured. Set one key in .env:\n"
            "  TAVILY_API_KEY  |  SERPAPI_API_KEY  |  BRAVE_API_KEY  |  "
            "GOOGLE_CSE_API_KEY + GOOGLE_CSE_CX\n")
    print(f"provider: {provider}\n")
    print(f"raw results for {query!r}:")
    for r in search(query, num=5):
        print(f"  {r['url']}\n     {r['title']}")
    print(f"\ndiscovered profiles for {query!r}:")
    for platform, url in find_profiles(query).items():
        print(f"  {platform:10} {url}")
