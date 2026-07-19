"""LinkedIn handling — compliant by design (NO scraping).

READ THIS BEFORE USING. Unlike the other sources here, LinkedIn has no
free/DIY way to fetch member profiles:

  * The official API does not grant arbitrary member-profile lookups (it is
    gated to approved enterprise partners).
  * Scraping is prohibited by LinkedIn's User Agreement REGARDLESS of the data
    being public, and is actively enforced (IP bans + lawsuits; LinkedIn sued
    and shut down the Proxycurl data API in 2025).
  * Emails are essentially never on a profile anyway.

So this module deliberately does NOT scrape. It offers three compliant paths:

  1. `public_urls_from_enrichment` — collect the LinkedIn URLs people already
     published themselves (extracted by retrievers/websites.py). This is just
     reading a link the person put on their own site.

  2. `discover_urls` — find a person's public LinkedIn URL via a web search
     (retrievers/websearch.py). Discovering a public URL is fine; we do NOT then
     fetch the gated profile behind it.

  3. `enrich_via_provider` — an OPTIONAL hook for a *licensed* B2B enrichment
     provider you subscribe to (set LINKEDIN_PROVIDER_API_KEY). It is a stub:
     you supply the provider's endpoint. Using one is your decision and you are
     responsible for its terms and for GDPR/CCPA "legitimate interest".

-----------------------------------------------------------------------------
Scraper landscape (informational — NOT implemented here, and why):

  Tool / method       Reality in 2026                    Verdict
  -------------       --------------                     -------
  Playwright/Selenium needs a logged-in account; trips    account bans; breach of
   browser automation  LinkedIn's bot detection            User Agreement
  Proxycurl            was the popular LinkedIn data API   SUED by LinkedIn in 2025,
                                                            shut down — do not rely
  Bright Data / Apify  paid managed scrapers               ToS-grey; LinkedIn pushes
   "LinkedIn scrapers"                                     data brokers to delist
  Licensed B2B DBs     People Data Labs, Clearbit, etc.    legitimate IF licensed;
   (match, not scrape)  match a person to consented data    YOU carry privacy duty

  LinkedIn's User Agreement forbids automated collection regardless of the data
  being public, and it enforces with IP bans + civil suits. hiQ v. LinkedIn
  (CFAA) does NOT make scraping "allowed" — it only addressed criminal access,
  not the contract. Bottom line: no compliant DIY scraper exists; this module
  ships none. Use discover_urls (search) or a licensed provider you vet.
-----------------------------------------------------------------------------

Run:  python retrievers/linkedin.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def public_urls_from_enrichment(csv_name="producthunt_founder_web_enriched.csv"):
    """Return {name: linkedin_url} for LinkedIn links people published themselves."""
    out = {}
    path = config.data_path(csv_name)
    if not os.path.exists(path):
        return out
    for r in csv.DictReader(open(path)):
        if r.get("linkedin"):
            out[r.get("name") or r.get("username")] = r["linkedin"]
    return out


def discover_urls(name, context="founder"):
    """Find a person's public LinkedIn URL via web search (no scraping).

    Requires a web-search key (see retrievers/websearch.py). Returns the URL a
    search surfaced, or None. Verify before trusting — common names collide.
    """
    from retrievers import websearch
    return websearch.find_profiles(name, context=context, platforms=("linkedin",)).get("linkedin")


def enrich_via_provider(linkedin_url):
    """OPTIONAL: fetch a profile through a licensed provider you configure.

    This is intentionally a stub. If (and only if) you subscribe to a licensed
    provider, set LINKEDIN_PROVIDER_API_KEY and implement the request to that
    provider's documented endpoint here. Returns None when no key is set.
    """
    if not config.LINKEDIN_PROVIDER_API_KEY:
        return None
    raise NotImplementedError(
        "Plug in your licensed provider's endpoint here. This project ships no "
        "default provider on purpose — vendor choice and compliance are yours.")


if __name__ == "__main__":
    urls = public_urls_from_enrichment()
    print("LinkedIn is not scrapable here — see the module docstring.\n")
    print(f"Public LinkedIn URLs people published themselves ({len(urls)}):")
    for name, url in list(urls.items())[:30]:
        print(f"  {name:24} {url}")
    if not config.LINKEDIN_PROVIDER_API_KEY:
        print("\n(LINKEDIN_PROVIDER_API_KEY not set — provider enrichment disabled.)")
