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

def resolve_identity(candidates):
    """
    candidates: list of dicts with keys: name, github, twitter, linkedin, email, website
    returns canonical record with confidence
    """
    # naive merge: group by exact email, then website domain, then fuzzy name
    groups = {}
    for c in candidates:
        key = c.get("email") or domain_from_url(c.get("website") or "") or normalize_name(c.get("name") or "")
        groups.setdefault(key, []).append(c)
    # merge groups with fuzzy name similarity
    merged = []
    for k, group in groups.items():
        merged_record = {"names": list({g.get("name") for g in group}), "handles": {}, "evidence": group}
        for g in group:
            if g.get("github"): merged_record["handles"]["github"] = g.get("github")
            if g.get("twitter"): merged_record["handles"]["twitter"] = g.get("twitter")
            if g.get("linkedin"): merged_record["handles"]["linkedin"] = g.get("linkedin")
        merged.append(merged_record)
    return merged
