"""GitHub signal collector.

One collector, one job: turn a GitHub handle into the raw signals the Founder
Score needs — demonstrated capability (the code itself), building trajectory,
provenance, and traction. Stdlib only, so it runs with no dependencies and no
auth. Set GITHUB_TOKEN to raise the rate limit from 60 to 5000 requests/hour.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

API = "https://api.github.com"

# Extensions we treat as "source the founder actually wrote".
SOURCE_EXTS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".rb", ".swift", ".scala", ".ex",
    ".cs", ".php", ".sql", ".sh", ".m", ".mm",
)


class GitHubError(RuntimeError):
    pass


def _get(path):
    """GET a GitHub API path (or full URL). Returns parsed JSON."""
    url = path if path.startswith("http") else API + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "vc-brain-sourcing",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise GitHubError(f"GitHub 404 — not found: {url}") from e
        if e.code in (403, 429):
            raise GitHubError(
                "GitHub rate limit hit. Set GITHUB_TOKEN to raise it "
                "(60/hr unauthenticated -> 5000/hr with a token)."
            ) from e
        raise GitHubError(f"GitHub HTTP {e.code} for {url}") from e


def _parse_ts(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _days_ago(dt):
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).days


@dataclass
class RepoDetail:
    """The one repo we read closely — the capability engine's input."""
    name: str
    full_name: str
    url: str
    description: str
    languages: dict = field(default_factory=dict)
    size_kb: int = 0
    stars: int = 0
    forks: int = 0
    has_tests: bool = False
    has_ci: bool = False
    has_docs: bool = False
    readme: str = ""
    source_files: list = field(default_factory=list)  # [{path, content}]


@dataclass
class GitHubProfile:
    """Everything the scorer reads. Nothing derived here — just collected."""
    handle: str
    profile_url: str
    name: str
    bio: str
    location: str
    account_age_days: int
    followers: int
    owned_repos: list           # non-fork repos, richest metadata GitHub gives cheaply
    recent_push_events: int     # push events in the last ~90 days (GitHub's events window)
    active_repos_90d: int       # owned repos pushed to in the last 90 days
    orgs: list                  # org logins
    top_repo: RepoDetail | None # the repo we read closely


def _pick_top_repo(owned):
    """The founder's most substantial own project: real code, recently touched.

    Deliberately NOT ranked by stars — a clean 2-star repo beats a forked
    boilerplate with 500. Rank by (has real size) then recency then engagement.
    """
    def key(r):
        return (
            min(r.get("size", 0), 50_000),          # code volume, capped so one huge repo can't dominate
            -( _days_ago(_parse_ts(r.get("pushed_at"))) or 9999),  # recency
            r.get("stargazers_count", 0),
        )
    candidates = [r for r in owned if not r.get("fork") and r.get("size", 0) > 0]
    if not candidates:
        return None
    return max(candidates, key=key)


def _fetch_repo_detail(repo):
    owner = repo["owner"]["login"]
    name = repo["name"]
    full = repo["full_name"]
    branch = repo.get("default_branch", "main")

    detail = RepoDetail(
        name=name,
        full_name=full,
        url=repo.get("html_url", ""),
        description=repo.get("description") or "",
        size_kb=repo.get("size", 0),
        stars=repo.get("stargazers_count", 0),
        forks=repo.get("forks_count", 0),
    )

    # Languages (bytes per language).
    try:
        detail.languages = _get(f"/repos/{full}/languages")
    except GitHubError:
        detail.languages = {}

    # Full file tree in one request — used both for structure signals and to
    # pick source files to read.
    tree_paths = []
    try:
        tree = _get(f"/repos/{full}/git/trees/{branch}?recursive=1")
        tree_paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    except GitHubError:
        pass

    lowered = [p.lower() for p in tree_paths]
    detail.has_tests = any(("test" in p or "spec" in p) for p in lowered)
    detail.has_ci = any(p.startswith(".github/workflows/") for p in lowered)
    detail.has_docs = any(p.startswith("docs/") for p in lowered)

    # README.
    try:
        rd = _get(f"/repos/{full}/readme")
        if rd.get("encoding") == "base64":
            detail.readme = base64.b64decode(rd["content"]).decode("utf-8", "replace")
    except GitHubError:
        pass

    # Read up to 3 real source files (the actual capability signal).
    source_candidates = [
        p for p in tree_paths
        if p.lower().endswith(SOURCE_EXTS)
        and "test" not in p.lower()
        and "vendor/" not in p.lower()
        and "node_modules/" not in p.lower()
    ]
    # Prefer files that look like entrypoints/core logic, then anything.
    source_candidates.sort(key=lambda p: (p.count("/"), len(p)))
    for path in source_candidates[:3]:
        try:
            f = _get(f"/repos/{full}/contents/{path}?ref={branch}")
            if f.get("encoding") == "base64":
                content = base64.b64decode(f["content"]).decode("utf-8", "replace")
                detail.source_files.append({"path": path, "content": content})
        except GitHubError:
            continue

    return detail


def public_repos(handle, owned_only=False):
    """A user's public repos in one GitHub call. THE single place GitHub repo data
    is fetched — the ingestion-layer fetcher (services/) delegates here too."""
    query = "sort=pushed&per_page=100" + ("&type=owner" if owned_only else "")
    return _get(f"/users/{handle}/repos?{query}")


def collect(handle):
    """Collect a GitHubProfile for one handle. Raises GitHubError on failure."""
    user = _get(f"/users/{handle}")

    repos = public_repos(handle, owned_only=True)
    owned = [r for r in repos if not r.get("fork")]

    active_90 = sum(
        1 for r in owned
        if (_days_ago(_parse_ts(r.get("pushed_at"))) or 9999) <= 90
    )

    # Public events window is ~90 days / 300 events — a clean recent-velocity signal.
    try:
        events = _get(f"/users/{handle}/events/public?per_page=100")
        recent_pushes = sum(1 for e in events if e.get("type") == "PushEvent")
    except GitHubError:
        recent_pushes = 0

    try:
        orgs = [o["login"] for o in _get(f"/users/{handle}/orgs")]
    except GitHubError:
        orgs = []

    top = _pick_top_repo(owned)
    top_detail = _fetch_repo_detail(top) if top else None

    return GitHubProfile(
        handle=handle,
        profile_url=user.get("html_url", f"https://github.com/{handle}"),
        name=user.get("name") or handle,
        bio=user.get("bio") or "",
        location=user.get("location") or "",
        account_age_days=_days_ago(_parse_ts(user.get("created_at"))) or 0,
        followers=user.get("followers", 0),
        owned_repos=owned,
        recent_push_events=recent_pushes,
        active_repos_90d=active_90,
        orgs=orgs,
        top_repo=top_detail,
    )
