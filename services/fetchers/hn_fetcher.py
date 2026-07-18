import requests
from datetime import datetime

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"

def search_hackernews(query, tags=None, page=0):
    params = {"query": query, "page": page, "hitsPerPage": 50}
    if tags:
        params["tags"] = tags
    r = requests.get(ALGOLIA_URL, params=params)
    r.raise_for_status()
    return r.json()

def hn_signals_for_query(query):
    res = search_hackernews(query)
    hits = []
    for h in res.get("hits", []):
        hits.append({
            "title": h.get("title"),
            "points": h.get("points"),
            "num_comments": h.get("num_comments"),
            "url": h.get("url"),
            "objectID": h.get("objectID"),
            "created_at": h.get("created_at")
        })
    return {"query": query, "fetched_at": datetime.utcnow().isoformat(), "hits": hits}

if __name__ == "__main__":
    print(hn_signals_for_query("your-product-name"))
