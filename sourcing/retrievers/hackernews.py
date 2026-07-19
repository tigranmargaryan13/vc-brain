"""Hacker News retriever — search, items, users, and story lists.

No API key required, no meaningful rate limit. Two public APIs are used:
    Firebase v0  (hacker-news.firebaseio.com)  -> items, users, story lists
    Algolia      (hn.algolia.com)              -> full-text search

Run:  python retrievers/hackernews.py "your search text"
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

FIREBASE = "https://hacker-news.firebaseio.com/v0"
ALGOLIA = "https://hn.algolia.com/api/v1"
_session = requests.Session()
_session.headers["User-Agent"] = "sourcing/1.0"

STORY_LISTS = {"top": "topstories", "new": "newstories", "best": "beststories",
               "ask": "askstories", "show": "showstories", "job": "jobstories"}


def _get(url, params=None, retries=4):
    for attempt in range(retries):
        r = _session.get(url, params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


# ---- Firebase: items, users, lists
def get_item(item_id):
    return _get(f"{FIREBASE}/item/{item_id}.json")


def get_user(username):
    return _get(f"{FIREBASE}/user/{username}.json")


def get_items(item_ids, max_workers=16):
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return [it for it in pool.map(get_item, item_ids) if it]


def get_stories(list_type="top", limit=30):
    ids = _get(f"{FIREBASE}/{STORY_LISTS[list_type]}.json")[:limit]
    return get_items(ids)


# ---- Algolia: search
def search(query="", tags=None, numeric_filters=None, by_date=False,
           hits_per_page=50, max_pages=None):
    """Full-text search. `tags` e.g. 'story' or f'author_{name}'.
    `numeric_filters` e.g. ['points>100']."""
    endpoint = "search_by_date" if by_date else "search"
    params = {"query": query, "hitsPerPage": hits_per_page, "page": 0}
    if tags:
        params["tags"] = tags if isinstance(tags, str) else ",".join(tags)
    if numeric_filters:
        params["numericFilters"] = ",".join(numeric_filters)
    hits, page = [], 0
    while True:
        params["page"] = page
        data = _get(f"{ALGOLIA}/{endpoint}", params=params)
        hits.extend(data.get("hits", []))
        page += 1
        if page >= data.get("nbPages", 1) or (max_pages and page >= max_pages):
            return hits


def attention(query):
    """Earned-attention summary for a product/person name on HN."""
    hits = search(query, tags="story", max_pages=1)
    matched = [h for h in hits if query.lower() in (h.get("title") or "").lower()]
    return {"hits": len(matched),
            "peak_points": max((h["points"] for h in matched), default=0)}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"HN search: {q!r}\n")
        for h in search(q, tags="story", max_pages=1)[:10]:
            print(f"  [{h['points']:>4} pts] {h['title']}  "
                  f"(https://news.ycombinator.com/item?id={h['objectID']})")
    else:
        print("Top 5 stories:\n")
        for s in get_stories("top", 5):
            print(f"  [{s.get('score')} pts] {s.get('title')}  by {s.get('by')}")
