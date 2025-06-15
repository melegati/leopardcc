import requests
import base64
import json
from typing import List, Callable, Dict, Any
from datetime import datetime, timedelta
import os

GITHUB_API_URL = "https://api.github.com"
SEARCH_REPOS_ENDPOINT = f"{GITHUB_API_URL}/search/repositories"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.getenv('GITHUB_API_KEY')}"
}

def fetch_package_json(repo: dict) -> Dict[str, Any]:
    """Fetch and parse package.json content from a repo if it exists."""
    owner = repo['owner']['login']
    repo_name = repo['name']
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contents/package.json"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        content_data = response.json()
        if content_data.get("encoding") == "base64":
            content_str = base64.b64decode(content_data["content"]).decode("utf-8")
            return json.loads(content_str)
    return {}

def fetch_repos(query: str, per_page: int = 30, pages: int = 1) -> List[dict]:
    all_repos = []
    for page in range(1, pages + 1):
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page
        }
        response = requests.get(SEARCH_REPOS_ENDPOINT, headers=HEADERS, params=params)
        if response.status_code == 200:
            repos = response.json().get("items", [])
            all_repos.extend(repos)
        else:
            print(f"Error fetching page {page}: {response.status_code}")
            break
    return all_repos

def apply_filters(repos: List[dict], filters: List[Callable[[dict, Dict[str, Any]], bool]]) -> List[dict]:
    """Apply filters that may inspect the repo and its package.json content."""
    filtered = []
    for repo in repos:
        # print(f"Analyzing {repo['full_name']}")
        pkg = fetch_package_json(repo)
        if pkg:  # skip if no package.json
            if all(f(repo, pkg) for f in filters):
                filtered.append(repo)
    return filtered

def apply_filters_verbose(
    repos: List[dict],
    filters: List[tuple[Callable[[dict, Dict[str, Any]], bool], str]]
) -> List[dict]:
    """Apply filters to repositories and report failures."""
    passed = []
    for repo in repos:
        pkg = fetch_package_json(repo)
        if not pkg:
            print(f"[SKIP] {repo['full_name']} – no package.json")
            continue

        failed_reasons = []
        for filter in filters:
            try:
                func = filter[0]
                if not func(repo, pkg):
                    failed_reasons.append(filter[1])
            except Exception as e:
                failed_reasons.append(f"{filter[1]} (error: {e})")

        if failed_reasons:
            print(f"[EXCLUDED] {repo['full_name']} - Failed: {', '.join(failed_reasons)}")
        else:
            passed.append(repo)
            print(f"[✓ INCLUDED] {repo['full_name']}")
    return passed


# --- Example Filters ---

def has_dependency(dep_name: str) -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        return dep_name in deps or dep_name in dev_deps
    return filter_func, f"Project without dependency {dep_name}"

def has_script_name_like(script_name: str) -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        scripts = pkg.get("scripts", {})
        return any([script_name in script for script in scripts])
    return filter_func, f"Project without script named like {script_name}"

def has_script_content_like(content_like: str) -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        scripts = pkg.get("scripts", {})
        return any([content_like in content for content in scripts.values()])
    return filter_func, f"Project without script with content like {content_like}"

def exclude_topics(excluded_topics: List[str]) -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        owner = repo['owner']['login']
        repo_name = repo['name']
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/topics"
        response = requests.get(url, headers={**HEADERS, "Accept": "application/vnd.github.mercy-preview+json"})
        if response.status_code == 200:
            topics = response.json().get("names", [])
            return all([excluded_topic.lower() not in map(str.lower, topics) for excluded_topic in excluded_topics])
        return True  # fail open if topics can't be fetched
    return filter_func, f"Project with the topic(s) {', '.join(excluded_topics)}",

def has_recent_commit(days: int = 30) -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        owner = repo['owner']['login']
        repo_name = repo['name']
        branch = repo['default_branch']
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits/{branch}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code == 200:
            commit_data = response.json()
            commit_date_str = commit_data["commit"]["committer"]["date"]
            commit_date = datetime.strptime(commit_date_str, "%Y-%m-%dT%H:%M:%SZ")
            return commit_date >= datetime.now() - timedelta(days=days)
        return False  # If we can't fetch commits, assume inactive
    return filter_func, "Looks like a stale project"

BROWSER_DEPENDENCIES = {
    "react", "vue", "angular", "svelte", "next", "vite", "webpack",
    "babel", "tailwindcss", "emotion", "preact"
}

def excludes_browser_deps(pkg: dict) -> bool:
    deps = set(pkg.get("dependencies", {}).keys()) | set(pkg.get("devDependencies", {}).keys())
    return len(BROWSER_DEPENDENCIES & deps) == 0

def is_not_browser_script(pkg: dict) -> bool:
    scripts = pkg.get("scripts", {})
    suspicious = ["start", "dev", "serve"]
    return not any(key.lower() in scripts for key in suspicious)

def excludes_browser_keywords(pkg: dict) -> bool:
    keywords = map(str.lower, pkg.get("keywords", []))
    return all(kw not in keywords for kw in ["frontend", "web", "browser", "ui"])

def exclude_browser_projects() -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        return (
            excludes_browser_deps(pkg) and
            is_not_browser_script(pkg) and
            excludes_browser_keywords(pkg)
        )
    return filter_func, "Looks like a browser app"

def has_eslint_config(repo) -> bool:
    owner = repo['owner']['login']
    name = repo['name']
    url = f"{GITHUB_API_URL}/repos/{owner}/{name}/contents/eslint.config.js"
    response = requests.get(url, headers=HEADERS)
    return response.status_code == 200

def uses_eslint() -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    has_script_with_eslint =  has_script_content_like("eslint")
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        return (
            has_script_with_eslint[0](repo, pkg) or
            has_eslint_config(repo) 
        )
    return filter_func, "No eslint"

def has_test_coverage() -> tuple[Callable[[dict, Dict[str, Any]], bool], str]:
    has_coverage_script_by_name = has_script_name_like("cov")
    has_coverage_script_by_content = has_script_content_like("cov")
    def filter_func(repo: dict, pkg: Dict[str, Any]) -> bool:
        return (
            has_coverage_script_by_name[0](repo, pkg) or
            has_coverage_script_by_content[0](repo, pkg) 
        )
    return filter_func, "No test coverage"

# --- Main Program ---

def main():
    query = "language:JavaScript stars:>5000"
    print("Fetching repositories...")
    repos = fetch_repos(query, per_page=100, pages=20)  # Lower for testing
    print(f'Retrieved {len(repos)} repositories.')

    # Define filters
    filters = [
        has_script_name_like("test"),
        has_test_coverage(),
        uses_eslint(),
        exclude_topics(['algorithms', 'algorithm']),
        has_recent_commit(180),
        exclude_browser_projects()
    ]

    print("Applying filters based on package.json content...")
    filtered_repos = apply_filters_verbose(repos, filters)

    print(f"\nFiltered repositories (total: {len(filtered_repos)}):")
    for repo in filtered_repos:
        print(f"- {repo['full_name']} ({repo['stargazers_count']} ⭐)")

if __name__ == "__main__":
    main()
