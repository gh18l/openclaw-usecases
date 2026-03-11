"""Fetch OpenClaw use cases from Reddit using the public JSON API."""
import re
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

USECASE_KEYWORDS = [
    "use case", "workflow", "setup", "built", "automating", "automated",
    "i built", "i made", "i created", "i wrote", "sharing my", "my setup",
    "how i", "using openclaw", "openclaw to", "with openclaw",
]

SUBREDDITS = ["openclaw", "selfhosted", "LocalLLaMA", "AI_Agents"]

SEARCH_QUERIES = [
    ("openclaw use case", None),
    ("openclaw workflow", None),
    ("openclaw", "selfhosted"),
    ("openclaw", "LocalLLaMA"),
    ("openclaw", "AI_Agents"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 OpenClawUsecaseCollector/1.0",
    "Accept": "application/json",
}

CATEGORIES_KEYWORDS = {
    "Personal & Productivity": ["morning", "briefing", "calendar", "email", "reminder", "todo", "daily", "habit", "personal", "productivity", "schedule", "notification"],
    "Developer Tools": ["code", "developer", "git", "deploy", "ci/cd", "test", "debug", "api", "webhook", "devops", "programming", "documentation", "review"],
    "Business & Automation": ["business", "crm", "sales", "marketing", "invoice", "customer", "support", "report", "workflow", "automat", "enterprise", "slack"],
    "Smart Home & IoT": ["home", "iot", "sensor", "light", "thermostat", "smart", "device", "arduino", "raspberry", "mqtt"],
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


def is_usecase_post(title: str, selftext: str) -> bool:
    combined = (title + " " + selftext).lower()
    return any(kw in combined for kw in USECASE_KEYWORDS)


class RedditFetcher:
    BASE_URL = "https://www.reddit.com"

    def _get(self, url: str, params: dict = None) -> dict | None:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Reddit rate limited. Retry-After: {retry_after}s — skipping.")
                return None
            if resp.status_code in (403, 404):
                logger.warning(f"Reddit {resp.status_code} for {url}")
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Reddit request failed for {url}: {e}")
            return None

    def _parse_posts(self, data: dict, source_label: str) -> list[dict]:
        results = []
        posts = data.get("data", {}).get("children", [])
        for post in posts:
            p = post.get("data", {})
            title = p.get("title", "").strip()
            selftext = p.get("selftext", "") or ""
            score = p.get("score", 0)
            permalink = p.get("permalink", "")
            subreddit = p.get("subreddit", "")

            if score < 3:
                continue
            if not is_usecase_post(title, selftext):
                continue
            if not permalink:
                continue

            url = f"https://www.reddit.com{permalink}"
            description = selftext.strip()[:300] if selftext.strip() else title
            # Clean up reddit markdown artifacts
            description = re.sub(r"\n+", " ", description).strip()

            category = detect_category(f"{title} {description}")
            results.append({
                "id": make_id(url),
                "title": title,
                "description": description or "No description.",
                "url": url,
                "source": f"reddit/{subreddit}" if subreddit else source_label,
                "category": category,
                "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "score": score,
            })
        return results

    def fetch_subreddit_top(self, subreddit: str, limit: int = 100) -> list[dict]:
        url = f"{self.BASE_URL}/r/{subreddit}/top.json"
        data = self._get(url, params={"limit": limit, "t": "all"})
        if not data:
            return []
        results = self._parse_posts(data, f"reddit/{subreddit}")
        logger.info(f"r/{subreddit} top: {len(results)} use case posts found.")
        return results

    def fetch_search(self, query: str, subreddit: str = None, limit: int = 50) -> list[dict]:
        if subreddit:
            url = f"{self.BASE_URL}/r/{subreddit}/search.json"
            params = {"q": query, "restrict_sr": "1", "sort": "top", "t": "all", "limit": limit}
        else:
            url = f"{self.BASE_URL}/search.json"
            params = {"q": query, "sort": "top", "t": "all", "limit": limit}
        data = self._get(url, params=params)
        if not data:
            return []
        label = f"reddit/{subreddit}" if subreddit else "reddit-search"
        results = self._parse_posts(data, label)
        logger.info(f"Reddit search '{query}' (r/{subreddit or 'all'}): {len(results)} posts found.")
        return results

    def fetch_all(self) -> list[dict]:
        all_results = []

        # Top posts from openclaw subreddit
        all_results.extend(self.fetch_subreddit_top("openclaw", limit=100))
        time.sleep(2)

        # Searches
        for query, subreddit in SEARCH_QUERIES:
            all_results.extend(self.fetch_search(query, subreddit, limit=50))
            time.sleep(2)

        return all_results
