import re
from rapidfuzz import fuzz
from urllib.parse import urlparse

def normalize_name(name):
    return re.sub(r'\s+', ' ', name.strip().lower())

def domain_from_url(url):
    try:
        return urlparse(url).netloc.replace('www.', '')
    except:
        return None

def fuzzy_match(a, b, threshold=85):
    return fuzz.token_sort_ratio(a, b) >= threshold

HANDLE_KEYS = ("github", "twitter", "linkedin")

def _linked(a, b):
    # two raw signals belong to the same person if they share ANY identifier
    if a.get("email") and a.get("email") == b.get("email"):
        return True
    da, db = domain_from_url(a.get("website") or ""), domain_from_url(b.get("website") or "")
    if da and da == db:
        return True
    for h in HANDLE_KEYS:
        if a.get(h) and a.get(h) == b.get(h):
            return True
    na, nb = normalize_name(a.get("name") or ""), normalize_name(b.get("name") or "")
    # fuzzy name is the weakest link: distinct people can share a name
    return bool(na and nb and fuzzy_match(na, nb))

def resolve_identity(candidates):
    """
    candidates: list of dicts with keys: name, github, twitter, linkedin, email, website
    returns canonical records with merged handles and the raw signals as evidence
    """
    # union-find over pairwise links; O(n^2) is fine at hackathon scale
    parent = list(range(len(candidates)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            if _linked(candidates[i], candidates[j]):
                parent[find(i)] = find(j)

    groups = {}
    for i, c in enumerate(candidates):
        groups.setdefault(find(i), []).append(c)

    merged = []
    for group in groups.values():
        record = {"names": sorted({g.get("name") for g in group if g.get("name")}),
                  "handles": {}, "evidence": group}
        for g in group:
            for h in HANDLE_KEYS:
                if g.get(h):
                    record["handles"][h] = g[h]
        merged.append(record)
    return merged
