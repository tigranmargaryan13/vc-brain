"""Twitter / X retriever — the OFFICIAL API (the compliant path).

Set X_BEARER_TOKEN in .env. There is NO free tier since Feb 2026: X uses
pay-per-use (~$0.010 per user lookup, ~$0.005 per tweet read). For ~50 founder
handles that is cents, but you must enable billing and create a bearer token at
https://developer.x.com. This module reads public profiles + recent tweets,
which maps to intent signals (bio "building/stealth" tells, follower counts).

-----------------------------------------------------------------------------
Scraper landscape (informational — NOT implemented here, and why):

  Tool / method      Status in 2026                     Verdict
  -------------      --------------                     -------
  snscrape           largely broken since X locked the  unreliable; ToS-violating
                     public GraphQL/JSON endpoints
  twscrape           works via logged-in account cookies risky: needs real/burner
                                                          accounts, gets them banned
  Nitter instances   mostly dead / rate-limited          unreliable
  Bright Data / SERP paid proxies + parsing              costly; ToS-grey; fragile

  These circumvent X's access controls and its Terms; X blocks them aggressively
  and they break constantly. This toolkit does not ship them. If you need Twitter
  data, the official API above is the durable, compliant route. To *discover* a
  person's public X URL without any Twitter access at all, use
  retrievers/websearch.py.
-----------------------------------------------------------------------------

Run:  python retrievers/twitter.py naval
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

BASE = "https://api.twitter.com/2"
_session = requests.Session()

USER_FIELDS = ("description,public_metrics,location,url,verified,created_at,"
               "profile_image_url,entities")


def _headers():
    if not config.X_BEARER_TOKEN:
        raise RuntimeError(
            "X_BEARER_TOKEN not set. The X API has no free tier (pay-per-use since "
            "Feb 2026). Create a token at https://developer.x.com after enabling "
            "billing, then add X_BEARER_TOKEN to your .env.")
    return {"Authorization": f"Bearer {config.X_BEARER_TOKEN}"}


def get_user(username):
    """Public profile: bio, followers/following, location, url, verified."""
    r = _session.get(f"{BASE}/users/by/username/{username.lstrip('@')}",
                     headers=_headers(), params={"user.fields": USER_FIELDS}, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("data")


def get_recent_tweets(user_id, max_results=10):
    """Up to `max_results` recent tweets for a user id (from get_user)."""
    r = _session.get(f"{BASE}/users/{user_id}/tweets", headers=_headers(),
                     params={"max_results": max_results,
                             "tweet.fields": "created_at,public_metrics"}, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def profile_summary(username):
    """Compact profile + engagement signal for one handle."""
    user = get_user(username)
    if not user:
        return None
    m = user.get("public_metrics", {})
    return {
        "username": user["username"], "name": user["name"],
        "bio": user.get("description"), "location": user.get("location"),
        "url": user.get("url"), "verified": user.get("verified"),
        "followers": m.get("followers_count"), "following": m.get("following_count"),
        "tweets": m.get("tweet_count"),
        "profile_url": f"https://x.com/{user['username']}",
    }


if __name__ == "__main__":
    handle = sys.argv[1] if len(sys.argv) > 1 else "naval"
    try:
        info = profile_summary(handle)
    except RuntimeError as err:
        raise SystemExit(f"\n{err}\n")
    if not info:
        raise SystemExit(f"@{handle} not found")
    print(f"{info['name']} (@{info['username']}){'  ✓' if info['verified'] else ''}")
    print(f"  {info['followers']} followers | {info['following']} following | "
          f"{info['tweets']} tweets | {info['location'] or '?'}")
    print(f"  bio: {info['bio']}")
