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
    "Smart Home & IoT": ["home", "iot", "sensor", "light", "thermostat", "smart", "device", "arduino", "raspberry", "mqtt", "automation home"],
    "Content & Media": ["content", "blog", "social media", "twitter", "youtube", "video", "podcast", "newsletter", "writing", "media", "post", "publish"],
    "Finance & Trading": ["finance", "trading", "stock", "crypto", "budget", "expense", "invoice", "payment", "investment", "portfolio", "price"],
    "Multi-Agent Systems": ["multi-agent", "multi agent", "orchestrat", "agent", "pipeline", "chain", "crew", "swarm", "coordinator", "supervisor"],
}


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
        """Fetch use cases from hesamsheikh/awesome-openclaw-usecases."""
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
            time.sleep(0.1)  # gentle rate limiting

        logger.info(f"Fetched {len(results)} use cases from awesome-openclaw-usecases.")
        return results

    def fetch_search_repos(self, query: str) -> list[dict]:
        """Search GitHub repos matching query."""
        results = []
        url = f"{self.BASE_URL}/search/repositories"
        data = self._get(url, params={"q": query, "sort": "stars", "per_page": 30})
        if not data or "items" not in data:
            return results

        for repo in data["items"]:
            title = repo.get("full_name", "")
            description = repo.get("description") or ""
            html_url = repo.get("html_url", "")
            stars = repo.get("stargazers_count", 0)
            if not html_url or not title:
                continue
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

        logger.info(f"Search '{query}': {len(results)} repos found.")
        return results

    def fetch_all(self) -> list[dict]:
        all_results = []
        all_results.extend(self.fetch_awesome_usecases())
        for query in ["openclaw use case", "openclaw workflow"]:
            all_results.extend(self.fetch_search_repos(query))
            time.sleep(1)
        return all_results
