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

# All repo search queries
REPO_SEARCH_QUERIES = [
    "openclaw use case",
    "openclaw workflow",
    "openclaw agent",
    "openclaw automation",
    "openclaw n8n",
    "openclaw tutorial",
    "openclaw example",
    "openclaw integration",
    "built with openclaw",
    "openclaw project",
    "openclaw template",
    "openclaw pipeline",
]

# Code/README search queries (searches file contents)
CODE_SEARCH_QUERIES = [
    "openclaw use case in:readme",
    "openclaw workflow in:readme",
    "openclaw automation in:readme",
    "openclaw agent in:readme",
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
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    logger.warning(f"Rate limited. Retry-After: {retry_after}s — skipping.")
                else:
                    logger.warning(f"403 Forbidden for {url} — skipping.")
                return None
            if resp.status_code == 404:
                logger.warning(f"404 Not Found: {url}")
                return None
            if resp.status_code == 422:
                logger.warning(f"422 Unprocessable for {url} — skipping.")
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
            "description": description[:300] if description else "No description available.",
            "url": url,
            "source": "awesome-openclaw-usecases",
            "category": category,
            "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    def fetch_awesome_usecases(self) -> list[dict]:
        """Fetch all use cases from hesamsheikh/awesome-openclaw-usecases."""
        results = []
        url = f"{self.BASE_URL}/repos/hesamsheikh/awesome-openclaw-usecases/contents/usecases"
        items = self._get(url)
        if not items:
            logger.warning("Could not fetch awesome-openclaw-usecases contents.")
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
                content = resp.text
            except requests.RequestException as e:
                logger.warning(f"Failed to download {raw_url}: {e}")
                continue

            parsed = self._parse_markdown(content, html_url, name)
            if parsed:
                results.append(parsed)
            time.sleep(0.1)

        logger.info(f"Fetched {len(results)} use cases from awesome-openclaw-usecases.")
        return results

    def fetch_search_repos_paginated(self, query: str, max_pages: int = 10) -> list[dict]:
        """Search GitHub repos with pagination (up to 1000 results per query)."""
        results = []
        seen_urls = set()
        url = f"{self.BASE_URL}/search/repositories"

        for page in range(1, max_pages + 1):
            data = self._get(url, params={"q": query, "sort": "stars", "per_page": 100, "page": page})
            if not data or "items" not in data:
                break

            items = data["items"]
            if not items:
                break

            for repo in items:
                html_url = repo.get("html_url", "")
                if not html_url or html_url in seen_urls:
                    continue
                seen_urls.add(html_url)
                title = repo.get("full_name", "")
                description = repo.get("description") or ""
                stars = repo.get("stargazers_count", 0)
                category = detect_category(f"{title} {description}")
                results.append({
                    "id": make_id(html_url),
                    "title": title,
                    "description": f"{description} ⭐ {stars}" if description else f"GitHub repo · ⭐ {stars}",
                    "url": html_url,
                    "source": "github-search",
                    "category": category,
                    "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })

            total_count = data.get("total_count", 0)
            fetched_so_far = page * 100
            logger.info(f"  Repo search '{query}' page {page}: {len(items)} items (total: {total_count})")

            if fetched_so_far >= min(total_count, 1000):
                break

            # Respect secondary rate limit: 1 req/sec for search
            time.sleep(1.2)

        logger.info(f"Repo search '{query}': {len(results)} total repos fetched.")
        return results

    def fetch_code_search_paginated(self, query: str, max_pages: int = 10) -> list[dict]:
        """Search GitHub code (README contents) with pagination."""
        if not self.authenticated:
            logger.info(f"Skipping code search '{query}' — requires authentication.")
            return []

        results = []
        seen_urls = set()
        url = f"{self.BASE_URL}/search/code"

        for page in range(1, max_pages + 1):
            data = self._get(url, params={"q": query, "per_page": 100, "page": page})
            if not data or "items" not in data:
                break

            items = data["items"]
            if not items:
                break

            for item in items:
                repo = item.get("repository", {})
                html_url = repo.get("html_url", "")
                if not html_url or html_url in seen_urls:
                    continue
                seen_urls.add(html_url)
                title = repo.get("full_name", "")
                description = repo.get("description") or ""
                category = detect_category(f"{title} {description}")
                results.append({
                    "id": make_id(html_url),
                    "title": title,
                    "description": description[:300] if description else "Found via README search.",
                    "url": html_url,
                    "source": "github-code-search",
                    "category": category,
                    "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })

            total_count = data.get("total_count", 0)
            fetched_so_far = page * 100
            logger.info(f"  Code search '{query}' page {page}: {len(items)} items (total: {total_count})")

            if fetched_so_far >= min(total_count, 1000):
                break

            time.sleep(1.2)

        logger.info(f"Code search '{query}': {len(results)} repos fetched.")
        return results

    def fetch_all(self) -> list[dict]:
        all_results = []
        seen_urls = set()

        def add_deduped(items):
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)

        # Primary source
        add_deduped(self.fetch_awesome_usecases())

        # Repo searches (paginated)
        for query in REPO_SEARCH_QUERIES:
            add_deduped(self.fetch_search_repos_paginated(query, max_pages=10))
            time.sleep(1.5)

        # Code/README searches (paginated, auth only)
        for query in CODE_SEARCH_QUERIES:
            add_deduped(self.fetch_code_search_paginated(query, max_pages=10))
            time.sleep(1.5)

        logger.info(f"GitHub total (deduplicated): {len(all_results)} items.")
        return all_results
