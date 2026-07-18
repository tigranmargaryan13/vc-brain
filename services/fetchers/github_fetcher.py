import os, requests, time
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def fetch_repos_by_username(username):
    url = f"https://api.github.com/users/{username}/repos?per_page=100"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def fetch_commit_count(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        # use Link header to estimate total pages if needed; simple fallback:
        return len(resp.json())
    return 0

def github_signals_for_username(username):
    repos = fetch_repos_by_username(username)
    signals = []
    for r in repos:
        signals.append({
            "repo": r["name"],
            "full_name": r["full_name"],
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "language": r.get("language"),
            "updated_at": r["updated_at"],
            "html_url": r["html_url"]
        })
    return {"username": username, "fetched_at": datetime.utcnow().isoformat(), "repos": signals}

# Example usage: write to raw_signals table (psycopg2 or SQLAlchemy)
if __name__ == "__main__":
    print(github_signals_for_username("octocat"))
