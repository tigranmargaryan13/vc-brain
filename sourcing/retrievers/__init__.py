"""Data-collection retrievers, one module per public source.

    luma         Luma events (dinners) + their guests and hosts   [no key]
    producthunt  Product Hunt launches + makers/hunters            [PH keys]
    github       GitHub user profiles + repositories               [optional token]
    hackernews   Hacker News search / items / users                [no key]
    domains      Domain registration age via RDAP                  [no key]
    websites     Personal-site enrichment (bio/email/socials)      [no key]
    websearch    Discover public profile URLs (Tavily/SerpAPI/…)   [one search key]
    twitter      Official X API (+ scraper landscape notes)        [paid X token]
    linkedin     Compliant LinkedIn handling (no scraping)         [optional provider]

Run any module from the package root, e.g.:  python retrievers/hackernews.py
"""
