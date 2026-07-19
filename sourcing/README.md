# Founder Sourcing — data collection toolkit

Comprehensive, self-contained scripts for collecting public founder / product /
event data from several sources, plus a small analysis pipeline built on top.

Each **retriever** is one clean module for one source. Everything writes to
`data/`. API keys (where needed) are read from a git-ignored `.env` — no secret
is stored in the code.

---

## Directory layout

```
sourcing/
├── README.md              ← you are here
├── config.py              ← central config: data path + API keys (from .env)
├── .env.example           ← copy to .env and fill in your keys (all blank)
├── requirements.txt
├── data/                  ← all CSV / JSON outputs land here
├── retrievers/            ← one module per data source (the collectors)
│   ├── luma.py            ← events (dinners) + guests + hosts
│   ├── producthunt.py     ← launched products + makers/hunters
│   ├── github.py          ← user profiles + repositories
│   ├── hackernews.py      ← search / items / users
│   ├── domains.py         ← domain registration age (RDAP)
│   ├── websites.py        ← personal-site enrichment (bio/email/socials)
│   ├── websearch.py       ← discover public profile URLs (Tavily/SerpAPI/…)
│   ├── twitter.py         ← official X API (+ scraper landscape notes)
│   └── linkedin.py        ← compliant LinkedIn handling (no scraping)
└── pipeline/              ← analysis built on the collected data
    ├── producthunt_features.py   ← map PH data onto scoring criteria
    ├── founder_enrichment.py     ← cross-source founder record + coverage map
    ├── find_founders.py          ← classify PH people as actual founders
    ├── dinner_founders.py        ← classify dinner guests as actual founders
    ├── join_founders.py          ← merge PH + dinner founders into one CSV
    └── founder_product_info.py   ← product / industry / location / repo per founder
```

---

## Quick start

```bash
cd sourcing
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit .env and add any keys you have

# run any retriever (from the sourcing/ folder):
python retrievers/hackernews.py "ai agents"     # no key needed
python retrievers/domains.py stripe.com         # no key needed
python retrievers/producthunt.py                # needs Product Hunt keys
```

---

## API keys — what each source needs

Keys live in `.env` (copy from `.env.example`). **All are blank by default.**

| Source | Env var(s) | Required? | Cost | Where to get it |
|---|---|---|---|---|
| **Hacker News** | — | No | Free | No account, no limits |
| **Luma** (dinners/guests) | — | No | Free | Public discovery endpoint |
| **Domains** (RDAP) | — | No | Free | Public registry data |
| **Websites** | — | No | Free | Fetches public pages |
| **GitHub** | `GITHUB_TOKEN` | Optional | Free | [github.com/settings/tokens](https://github.com/settings/tokens) — lifts 60→5000 req/hr |
| **Product Hunt** | `PRODUCTHUNT_CLIENT_ID` + `PRODUCTHUNT_CLIENT_SECRET` (or `PRODUCTHUNT_TOKEN`) | **Yes** | Free* | [producthunt.com/v2/oauth/applications](https://www.producthunt.com/v2/oauth/applications) |
| **Web search** | one of `TAVILY_API_KEY` / `SERPAPI_API_KEY` / `BRAVE_API_KEY` / `GOOGLE_CSE_API_KEY`+`GOOGLE_CSE_CX` | Optional | Free tier | [tavily.com](https://tavily.com) · [serpapi.com](https://serpapi.com) · [brave.com/search/api](https://brave.com/search/api) |
| **Twitter / X** | `X_BEARER_TOKEN` | Optional | **Paid** (no free tier) | [developer.x.com](https://developer.x.com) — ~$0.01/lookup |
| **LinkedIn** | `LINKEDIN_PROVIDER_API_KEY` | Optional | Paid | A **licensed** enrichment provider only — see below |

\* Product Hunt is free but non-commercial by default (email hello@producthunt.com
for business use) and rate-limited to 6250 GraphQL complexity points / 15 min.

### Getting Product Hunt keys
1. Go to [producthunt.com/v2/oauth/applications](https://www.producthunt.com/v2/oauth/applications) → **Add an application**.
2. Name it anything. **Redirect URI** must be an absolute **https** URL (e.g. `https://localhost:8000/callback`) — it is unused by this flow. **Client type: Confidential.**
3. Copy the **API Key** and **API Secret** into `.env` as `PRODUCTHUNT_CLIENT_ID` and `PRODUCTHUNT_CLIENT_SECRET`.

---

## Retrievers

### `luma.py` — dinners + guests + hosts  *(no key)*
Pulls every public event in a city bounding box (default: NYC), filters for
dinners, then reads each event's **hosts** and publicly-shown **guests** (name,
bio, socials, Luma profile). Guest lists are capped at ~10 by Luma and only
appear when the host enabled them; **emails are never public**.
```bash
python retrievers/luma.py
# -> data/nyc_dinners.csv, data/nyc_dinner_guests.csv
```

### `producthunt.py` — launches + team  *(Product Hunt keys)*
Pulls launched products with metrics (votes, comments, reviews, topics) and
every **maker** (team) and **hunter**, including each person's products-launched
count.
```bash
python retrievers/producthunt.py
# -> data/producthunt_launch_teams.csv
```

### `github.py` — profiles + repos  *(optional token)*
Profile (name, company, location, bio, followers) plus top repositories (stars,
languages). `resolve_user()` verifies a handle really belongs to a person before
attaching their repos.
```bash
python retrievers/github.py torvalds
```

### `hackernews.py` — search / items / users  *(no key)*
Full-text search across all of HN (Algolia) plus canonical items/users/story
lists (Firebase).
```bash
python retrievers/hackernews.py "your search text"
```

### `domains.py` — registration age  *(no key)*
RDAP lookup of a domain's registration date → a "fresh domain" intent signal.
Follows Product Hunt `/r/` redirects to the real product domain first.
```bash
python retrievers/domains.py zoodata.ai
```

### `websites.py` — personal-site enrichment  *(no key)*
Fetches a person's own published site and extracts bio, contact email, and links
to their other socials (often including their LinkedIn/Twitter URLs).
```bash
python retrievers/websites.py https://example.com
```

### `websearch.py` — discover profile URLs  *(one search key)*
The compliant bridge to LinkedIn/Twitter. A web search returns public result
URLs (discovery is fine); it does **not** fetch the gated page behind them.
Pluggable across Tavily / SerpAPI / Brave / Google CSE — set one key.
```bash
python retrievers/websearch.py "Jane Doe founder"
# find_profiles(name) -> {"linkedin": ..., "twitter": ..., "github": ...}
```

### `twitter.py` — official X API  *(paid X_BEARER_TOKEN)*
Reads public profiles + recent tweets via the **official** API. No free tier
since Feb 2026 (~$0.01/lookup). The docstring documents the unofficial-scraper
landscape (snscrape, twscrape, Nitter) and why they aren't shipped here.
```bash
python retrievers/twitter.py naval
```

### `linkedin.py` — compliant handling  *(no scraping)*
**LinkedIn has no free/DIY API and scraping violates its terms (actively
enforced with lawsuits).** This module does **not** scrape. It (1) collects the
LinkedIn URLs people published themselves via `websites.py`, (2) discovers a
public LinkedIn URL via `websearch.py`, and (3) exposes an optional stub for a
*licensed* enrichment provider. See the module docstring for the full scraper
landscape and compliance rationale.

---

## Data outputs (`data/`)

| File | Produced by | Contents |
|---|---|---|
| `nyc_dinners.csv` | luma | Dinner events (name, time, venue) |
| `nyc_dinner_guests.csv` | luma | One row per guest/host with socials |
| `producthunt_launch_teams.csv` | producthunt | One row per (product, person) |
| `producthunt_founder_signals.{json,csv}` | pipeline/producthunt_features | PH signals mapped to scoring criteria |
| `producthunt_founder_web_enriched.csv` | pipeline (websites) | Founder bios/emails/socials from their sites |
| `founder_enriched.json` | pipeline/founder_enrichment | Cross-source founder record + coverage |
| `actual_founders.csv` | pipeline/find_founders | PH people classified as founders |
| `dinner_founders.csv` | pipeline/dinner_founders | Dinner guests classified as founders |
| `all_founders.csv` | pipeline/join_founders | PH + dinner founders merged |
| `founder_product_info.csv` | pipeline/founder_product_info | Product / industry / location / repo per founder |

---

## Twitter & LinkedIn scraping — the honest landscape

You asked about scrapers; here is the straight version. **This toolkit ships no
platform scraper**, on purpose — for both compliance and reliability. What
actually exists:

**Twitter / X**

| Approach | Reality (2026) | Verdict |
|---|---|---|
| Official X API (`twitter.py`) | Pay-per-use, ~$0.01/lookup | ✅ durable, compliant |
| `snscrape` | Broken since X locked public endpoints | ❌ unreliable, ToS-violating |
| `twscrape` | Works via logged-in account cookies | ⚠️ needs burner accounts, get banned |
| Nitter instances | Mostly dead / rate-limited | ❌ unreliable |

**LinkedIn**

| Approach | Reality (2026) | Verdict |
|---|---|---|
| Official API | No arbitrary profile lookups (partner-gated) | — not usable for this |
| Browser automation (Playwright/Selenium) | Needs login; trips bot detection | ❌ account bans, ToS breach |
| Proxycurl | **Sued by LinkedIn in 2025, shut down** | ❌ gone |
| Bright Data / Apify scrapers | Paid, ToS-grey, fragile | ⚠️ legal risk |
| Licensed B2B DB (People Data Labs, Clearbit…) | Match to consented data, not scrape | ⚠️ legit if licensed; you carry privacy duty |

**The compliant pattern this toolkit uses instead:**
`websearch.find_profiles(name)` → discovers the public profile **URL** →
`websites.enrich()` reads what the person published on **their own** site.
Discovering a link and reading someone's own website is fine; automating access
to a gated platform against its Terms is not. For richer LinkedIn fields, a
*licensed* provider (via `linkedin.enrich_via_provider`) is the only route that
isn't a ToS/legal liability — and the privacy-law obligation is yours.

## Compliance & rate limits (read me)

- **Cold-start rule:** absence of a signal means *unknown*, never *negative*.
- **LinkedIn:** not scraped here, by design. The only compliant paths are public
  URLs people publish themselves, or a licensed provider (your terms/GDPR duty).
- **Twitter/X:** the API has no free tier since Feb 2026 (pay-per-use, ~$0.01 per
  profile lookup). Not included as a retriever; add one against the official API
  if you enable billing.
- **Product Hunt:** free but non-commercial by default; respect the complexity
  rate limit (handled with backoff in the code).
- **GitHub:** 60 req/hr without a token, 5000 with one.
- **Politeness:** retrievers sleep between requests and back off on 429/5xx. Keep
  it that way — these are unofficial/public endpoints in several cases.
- This toolkit collects **public** data about people. Use it for evaluating who
  to reach out to, not for spam or profiling that a person wouldn't expect.
