"""Product Hunt retriever — launched products with their makers and hunters.

Requires authentication (Product Hunt has no anonymous API). Set either
PRODUCTHUNT_CLIENT_ID + PRODUCTHUNT_CLIENT_SECRET (exchanged for an app token
automatically) or a PRODUCTHUNT_TOKEN developer token. See config.py / README.

Free to use, rate-limited to 6250 GraphQL "complexity points" per 15 minutes.
Note: the top-level `user` query is redacted at the client-credentials tier, so
per-person data (incl. products-launched count) is read nested inside a post.

Run:  python retrievers/producthunt.py
"""

import csv
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"
TOKEN_URL = "https://api.producthunt.com/v2/oauth/token"

USER_FIELDS = """
    id name username headline twitterUsername websiteUrl profileImage url
    isMaker madePosts { totalCount }
"""
POST_FIELDS = f"""
    id name slug tagline description url website votesCount commentsCount
    reviewsRating reviewsCount createdAt featuredAt
    topics(first: 10) {{ edges {{ node {{ name }} }} }}
    makers {{ {USER_FIELDS} }}
    user {{ {USER_FIELDS} }}
"""

_session = requests.Session()
_token = {"value": None}


class ProductHuntError(RuntimeError):
    pass


def get_token():
    """Exchange client credentials for an app access token."""
    if config.PRODUCTHUNT_TOKEN:
        return config.PRODUCTHUNT_TOKEN
    if not (config.PRODUCTHUNT_CLIENT_ID and config.PRODUCTHUNT_CLIENT_SECRET):
        raise RuntimeError(
            "Missing Product Hunt credentials. Set PRODUCTHUNT_CLIENT_ID + "
            "PRODUCTHUNT_CLIENT_SECRET (or PRODUCTHUNT_TOKEN) in your .env. "
            "Create an app at https://www.producthunt.com/v2/oauth/applications")
    resp = _session.post(TOKEN_URL, json={
        "client_id": config.PRODUCTHUNT_CLIENT_ID,
        "client_secret": config.PRODUCTHUNT_CLIENT_SECRET,
        "grant_type": "client_credentials"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def graphql(query, variables=None, retries=4):
    if not _token["value"]:
        _token["value"] = get_token()
    headers = {"Authorization": f"Bearer {_token['value']}",
               "Content-Type": "application/json", "Accept": "application/json"}
    for attempt in range(retries):
        resp = _session.post(GRAPHQL_URL, json={"query": query,
                             "variables": variables or {}}, headers=headers, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = int(resp.headers.get("X-Rate-Limit-Reset", 2 ** attempt))
            print(f"Rate limited ({resp.status_code}); waiting {min(wait, 90)}s")
            time.sleep(min(wait, 90) + 1)
            continue
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise ProductHuntError(payload["errors"])
        return payload["data"]
    resp.raise_for_status()


def get_posts(order="RANKING", featured=True, topic=None, limit=20):
    """Retrieve launched products (each with its makers)."""
    query = f"""
    query($first:Int,$after:String,$order:PostsOrder,$featured:Boolean,$topic:String) {{
      posts(first:$first, after:$after, order:$order, featured:$featured, topic:$topic) {{
        edges {{ node {{ {POST_FIELDS} }} }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}"""
    posts, after = [], None
    while True:
        n = 20 if limit is None else min(20, limit - len(posts))
        conn = graphql(query, {"first": n, "after": after, "order": order,
                               "featured": featured, "topic": topic})["posts"]
        posts.extend(e["node"] for e in conn["edges"])
        if (limit is not None and len(posts) >= limit) or not conn["pageInfo"]["hasNextPage"]:
            return posts[:limit] if limit else posts
        after = conn["pageInfo"]["endCursor"]


def get_post(slug=None, id=None):
    query = f"query($slug:String,$id:ID){{ post(slug:$slug,id:$id){{ {POST_FIELDS} }} }}"
    return graphql(query, {"slug": slug, "id": id})["post"]


def products_launched(person):
    return ((person or {}).get("madePosts") or {}).get("totalCount", 0)


def flatten(posts):
    """One row per (product, person) with product metrics + person fields."""
    rows = []
    for p in posts:
        topics = "; ".join(e["node"]["name"] for e in p["topics"]["edges"])
        base = {"product": p["name"], "tagline": p["tagline"],
                "votes": p["votesCount"], "comments": p["commentsCount"],
                "reviews": p["reviewsCount"], "topics": topics,
                "featured_at": (p.get("featuredAt") or "")[:10],
                "product_url": (p["url"] or "").split("?")[0], "website": p["website"]}
        for role, person in [("hunter", p["user"])] + [("maker", m) for m in p["makers"]]:
            rows.append({**base, "role": role, "person": person["name"],
                         "username": person["username"], "headline": person.get("headline"),
                         "products_launched": products_launched(person),
                         "twitter": person.get("twitterUsername"),
                         "website_personal": person.get("websiteUrl"),
                         "ph_profile": (person["url"] or "").split("?")[0]})
    return rows


if __name__ == "__main__":
    try:
        posts = get_posts(order="RANKING", featured=True, limit=20)
    except RuntimeError as err:
        raise SystemExit(f"\n{err}\n")

    rows = flatten(posts)
    cols = ["product", "tagline", "votes", "comments", "reviews", "topics",
            "featured_at", "product_url", "website", "role", "person", "username",
            "products_launched", "twitter", "website_personal", "headline", "ph_profile"]
    with open(config.data_path("producthunt_launch_teams.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    makers = sum(r["role"] == "maker" for r in rows)
    print(f"{len(posts)} launches, {len(rows)} people ({makers} makers)")
    print("  -> data/producthunt_launch_teams.csv")
