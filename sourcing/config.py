"""Central configuration for the sourcing package.

API keys are read from environment variables (or a local `.env` file, see
`.env.example`). They are EMPTY by default — nothing here is a secret. Fill
them in your own `.env`, which is git-ignored.

Which retrievers need which key:
    luma.py         -> none (public discovery endpoint)
    hackernews.py   -> none (public API)
    domains.py      -> none (public RDAP)
    websites.py     -> none (fetches public pages)
    github.py       -> GITHUB_TOKEN            (optional; 60->5000 req/hr)
    producthunt.py  -> PRODUCTHUNT_CLIENT_ID + PRODUCTHUNT_CLIENT_SECRET
                       (or PRODUCTHUNT_TOKEN)  (required)
    linkedin.py     -> LINKEDIN_PROVIDER_API_KEY (optional; only if you use a
                       licensed enrichment provider — see linkedin.py notes)
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


def _load_dotenv():
    """Minimal .env loader — no external dependency."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(name, default=""):
    return os.environ.get(name, default)


def data_path(name):
    """Absolute path to a file inside the package's data/ folder."""
    return str(DATA_DIR / name)


# --- API credentials (empty unless set in environment / .env) ---------------
GITHUB_TOKEN = env("GITHUB_TOKEN")                     # optional
PRODUCTHUNT_CLIENT_ID = env("PRODUCTHUNT_CLIENT_ID")   # required for producthunt
PRODUCTHUNT_CLIENT_SECRET = env("PRODUCTHUNT_CLIENT_SECRET")
PRODUCTHUNT_TOKEN = env("PRODUCTHUNT_TOKEN")           # alternative to id/secret
LINKEDIN_PROVIDER_API_KEY = env("LINKEDIN_PROVIDER_API_KEY")  # optional

# Twitter / X — official API only (no free tier; see retrievers/twitter.py)
X_BEARER_TOKEN = env("X_BEARER_TOKEN")

# Web search — set ONE provider's key; websearch.py auto-detects which is present
TAVILY_API_KEY = env("TAVILY_API_KEY")
SERPAPI_API_KEY = env("SERPAPI_API_KEY")
BRAVE_API_KEY = env("BRAVE_API_KEY")
GOOGLE_CSE_API_KEY = env("GOOGLE_CSE_API_KEY")
GOOGLE_CSE_CX = env("GOOGLE_CSE_CX")   # Google Custom Search engine id
