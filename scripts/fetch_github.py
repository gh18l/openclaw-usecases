"""Fetch OpenClaw use cases from GitHub sources."""
import os
import re
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CATEGORIES_KEYWORDS = {
    "Personal & Productivity": ["morning", "briefing", "calendar", "email", "reminder", "todo", "daily", "habit", "personal", "productivity", "schedule", "notification"],
    "Developer Tools": ["code", "developer", "git", "deploy", "ci/cd", "test", "debug", "api", "webhook", "devops", "programming", "documentation", "review"],
    "Business & Automation": ["business", "crm", "sales", "marketing", "invoice", "customer", "support", "report", "workflow", "automat", "enterprise", "slack"],
    "Smart Home & IoT": ["home", "iot", "sensor", "light", "thermostat", "smart", "device", "arduino", "raspberry", "mqtt"],
    "Content & Media": ["content", "blog", "social media", "twitter", "youtube", "video", "podcast", "newsletter", "writing", "media", "post", "publish"],
    "Finance & Trading": ["finance", "trading", "stock", "crypto", "budget", "expense", "invoice", "payment", "investment", "portfolio", "price"],
    "Multi-Agent Systems": ["multi-agent", "multi agent", "orchestrat", "agent", "pipeline", "chain", "crew", "swarm", "coordinator", "supervisor"],
}

# Focused queries only — generic terms like "openclaw agent" return too much noise
REPO_SEARCH_QUERIES = [
    "openclaw use case",
    "openclaw workflow",
    "openclaw example",
    "openclaw template",
    "openclaw tutorial",
    "openclaw demo",
    "openclaw starter",
    "built with openclaw",
]

CODE_SEARCH_QUERIES = [
    "openclaw use case in:readme",
    "openclaw workflow in:readme",
    "built with openclaw in:readme",
]


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for category, keywords in CATEGORIES_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return "Personal & Productivity"


def make_id(url: str) -> str:
    return re.sub(r"[^a-z0-9]", "-", url.lower())[:80]


def is_quality_repo(repo: dict) -> bool:
    """Keep only repos that look like genuine use cases / demos."""
    if repo.get("fork"):
        return False
    if not repo.get("description", "").strip():
        return False
    if repo.get("stargazers_count", 0) < 1:
        return False
    # Skip repos whose name/description has no openclaw signal
    name = (repo.get("full_name", "") + " " + repo.get("description", "")).lower()
    if "openclaw" not in name:
        return False
    return True


class GitHubFetcher:
    BASE_URL = "https://api.github.com"

    def __init__(self):
        token = os.environ.get("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github+json"}
        self.authenticated = bool(token)
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
            logger.info("Using authenticated GitHub API (5000 req/hr)")
        else:
            logger.info("Using unauthenticated GitHub API (60 req/hr)")

    def _get(self, url: str, params: dict = None) -> dict | list | None:
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=15)
            if resp.status_code == 403:
                logger.warning(f"Rate limited / forbidden: {url}")
                return None
            if resp.status_code in (404, 422):
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None

    def _parse_markdown(self, content: str, url: str, filename: str) -> dict | None:
        lines = content.strip().splitlines()
        title = filename.replace(".md", "").replace("-", " ").replace("_", " ").title()
        description = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
            elif stripped and not stripped.startswith("#") and not description:
                description = stripped
                break
        if not title:
            return None
        category = detect_category(f"{title} {description} {content[:500]}")
        return {
            "id": make_id(url),
            "title": title,
            "description": description[:200] if description else "No description available.",
            "url": url,
            "source": "awesome-openclaw-usecases",
            "category": category,
            "stars": 0,
            "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    def fetch_awesome_usecases(self) -> list[dict]:
        results = []
        url = f"{self.BASE_URL}/repos/hesamsheikh/awesome-openclaw-usecases/contents/usecases"
        items = self._get(url)
        if not items:
            return results
        for item in items:
            if not isinstance(item, dict) or item.get("type") != "file":
                continue
            name = item.get("name", "")
            if not name.endswith(".md"):
                continue
            raw_url = item.get("download_url")
            html_url = item.get("html_url", raw_url)
            if not raw_url:
                continue
            try:
                resp = requests.get(raw_url, timeout=15)
                resp.raise_for_status()
                parsed = self._parse_markdown(resp.text, html_url, name)
                if parsed:
                    results.append(parsed)
            except requests.RequestException:
                continue
            time.sleep(0.1)
        logger.info(f"awesome-openclaw-usecases: {len(results)} use cases.")
        return results

    def fetch_search_repos(self, query: str, max_pages: int = 3) -> list[dict]:
        """Top results only (sorted by stars) — quality over quantity."""
        results = []
        seen = set()
        for page in range(1, max_pages + 1):
            data = self._get(
                f"{self.BASE_URL}/search/repositories",
                params={"q": query, "sort": "stars", "per_page": 100, "page": page},
            )
            if not data or not data.get("items"):
                break
            for repo in data["items"]:
                if not is_quality_repo(repo):
                    continue
                url = repo.get("html_url", "")
                if url in seen:
                    continue
                seen.add(url)
                title = repo.get("full_name", "")
                desc = repo.get("description", "").strip()
                stars = repo.get("stargazers_count", 0)
                results.append({
                    "id": make_id(url),
                    "title": title,
                    "description": f"{desc[:180]}",
                    "url": url,
                    "source": "github",
                    "category": detect_category(f"{title} {desc}"),
                    "stars": stars,
                    "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })
            time.sleep(1.2)
        logger.info(f"Repo search '{query}': {len(results)} quality repos.")
        return results

    def fetch_code_search(self, query: str, max_pages: int = 3) -> list[dict]:
        if not self.authenticated:
            return []
        results = []
        seen = set()
        for page in range(1, max_pages + 1):
            data = self._get(
                f"{self.BASE_URL}/search/code",
                params={"q": query, "per_page": 100, "page": page},
            )
            if not data or not data.get("items"):
                break
            for item in data["items"]:
                repo = item.get("repository", {})
                url = repo.get("html_url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                title = repo.get("full_name", "")
                desc = repo.get("description", "") or ""
                results.append({
                    "id": make_id(url),
                    "title": title,
                    "description": desc[:180] if desc else "Found via README.",
                    "url": url,
                    "source": "github",
                    "category": detect_category(f"{title} {desc}"),
                    "stars": 0,
                    "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })
            time.sleep(1.2)
        logger.info(f"Code search '{query}': {len(results)} repos.")
        return results

    def fetch_all(self) -> list[dict]:
        all_results = []
        seen_urls = set()

        def add(items):
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)

        add(self.fetch_awesome_usecases())
        for q in REPO_SEARCH_QUERIES:
            add(self.fetch_search_repos(q, max_pages=3))
            time.sleep(1)
        for q in CODE_SEARCH_QUERIES:
            add(self.fetch_code_search(q, max_pages=2))
            time.sleep(1)

        logger.info(f"GitHub total: {len(all_results)} items.")
        return all_results
