import os, requests
from datetime import datetime

CRUNCHBASE_KEY = os.getenv("CRUNCHBASE_KEY")
BASE = "https://api.crunchbase.com/api/v4/entities/organizations"

def crunchbase_company_lookup(name):
    # Example: use the v4 search endpoint (adjust to actual API version and params)
    url = f"{BASE}/search"
    headers = {"X-Cb-User-Key": CRUNCHBASE_KEY}
    payload = {"query": name, "limit": 5}
    r = requests.post(url, json=payload, headers=headers)
    r.raise_for_status()
    return r.json()

def crunchbase_enrich_company(cb_uuid):
    url = f"https://api.crunchbase.com/api/v4/entities/organizations/{cb_uuid}"
    headers = {"X-Cb-User-Key": CRUNCHBASE_KEY}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    print(crunchbase_company_lookup("stripe"))
