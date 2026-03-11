"""Fetch OpenClaw use cases from Reddit — quality-filtered."""
import re
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Strong signals only — must look like a real use case post
STRONG_KEYWORDS = [
    "i built", "i made", "i created", "i wrote", "i automated",
    "sharing my", "my setup", "my workflow", "my use case",
    "how i use", "how i built", "how i automated",
    "use case", "real world", "production", "in production",
    "tutorial", "guide", "step by step", "walkthrough",
    "showcase", "demo", "example workflow",
]

# Subreddits where openclaw use cases actually appear
TOP_SUBREDDITS = [
    ("openclaw", 500),
    ("OpenClawUseCases", 500),
    ("LocalLLaMA", 200),
    ("AI_Agents", 200),
    ("selfhosted", 100),
    ("n8n", 100),
]

SEARCH_QUERIES = [
    ("openclaw use case", None),
    ("openclaw workflow", None),
    ("openclaw tutorial", None),
    ("openclaw", "LocalLLaMA"),
    ("openclaw", "AI_Agents"),
    ("openclaw", "selfhosted"),
    ("openclaw", "n8n"),
    ("openclaw", "OpenClawUseCases"),
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

MIN_SCORE = 10  # Only posts with real engagement


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for category, keywords in CATEGORIES_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return "Personal & Productivity"


def make_id(url: str) -> str:
    return re.sub(r"[^a-z0-9]", "-", url.lower())[:80]


def is_quality_post(title: str, selftext: str, score: int) -> bool:
    if score < MIN_SCORE:
        return False
    combined = (title + " " + selftext).lower()
    if "openclaw" not in combined:
        return False
    return any(kw in combined for kw in STRONG_KEYWORDS)


class RedditFetcher:
    BASE_URL = "https://www.reddit.com"

    def _get(self, url: str, params: dict = None) -> dict | None:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if resp.status_code == 429:
                logger.warning(f"Reddit rate limited — skipping {url}")
                return None
            if resp.status_code in (403, 404):
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Reddit request failed: {e}")
            return None

    def _parse_posts(self, data: dict, source_label: str) -> list[dict]:
        results = []
        for post in data.get("data", {}).get("children", []):
            p = post.get("data", {})
            title = p.get("title", "").strip()
            selftext = p.get("selftext", "") or ""
            score = p.get("score", 0)
            permalink = p.get("permalink", "")
            subreddit = p.get("subreddit", "")

            if not permalink or not is_quality_post(title, selftext, score):
                continue

            url = f"https://www.reddit.com{permalink}"
            # Clean description: first 200 chars of post body, or just title
            desc = re.sub(r"\n+", " ", selftext.strip())[:200] if selftext.strip() else ""

            results.append({
                "id": make_id(url),
                "title": title,
                "description": desc,
                "url": url,
                "source": f"reddit/{subreddit}" if subreddit else source_label,
                "category": detect_category(f"{title} {desc}"),
                "stars": score,  # use Reddit score as quality signal
                "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })
        return results

    def _fetch_paginated(self, url: str, params: dict, target: int, label: str) -> list[dict]:
        results = []
        seen = set()
        after = None
        fetched = 0
        while fetched < target:
            p = dict(params)
            p["limit"] = min(100, target - fetched)
            if after:
                p["after"] = after
            data = self._get(url, p)
            if not data:
                break
            posts_data = data.get("data", {})
            children = posts_data.get("children", [])
            if not children:
                break
            for item in self._parse_posts(data, label):
                if item["id"] not in seen:
                    seen.add(item["id"])
                    results.append(item)
            after = posts_data.get("after")
            fetched += len(children)
            if not after or len(children) < p["limit"]:
                break
            time.sleep(2)
        return results

    def fetch_subreddit_top(self, subreddit: str, target: int) -> list[dict]:
        results = self._fetch_paginated(
            f"{self.BASE_URL}/r/{subreddit}/top.json",
            {"t": "all"},
            target,
            f"reddit/{subreddit}",
        )
        logger.info(f"r/{subreddit}: {len(results)} quality posts.")
        return results

    def fetch_search(self, query: str, subreddit: str = None, target: int = 100) -> list[dict]:
        if subreddit:
            url = f"{self.BASE_URL}/r/{subreddit}/search.json"
            params = {"q": query, "restrict_sr": "1", "sort": "top", "t": "all"}
        else:
            url = f"{self.BASE_URL}/search.json"
            params = {"q": query, "sort": "top", "t": "all"}
        results = self._fetch_paginated(url, params, target, f"reddit/{subreddit or 'search'}")
        logger.info(f"Reddit search '{query}' ({subreddit or 'global'}): {len(results)} quality posts.")
        return results

    def fetch_all(self) -> list[dict]:
        all_results = []
        seen = set()

        def add(items):
            for item in items:
                if item["id"] not in seen:
                    seen.add(item["id"])
                    all_results.append(item)

        for subreddit, target in TOP_SUBREDDITS:
            add(self.fetch_subreddit_top(subreddit, target))
            time.sleep(2)

        for query, subreddit in SEARCH_QUERIES:
            add(self.fetch_search(query, subreddit, target=100))
            time.sleep(2)

        logger.info(f"Reddit total: {len(all_results)} quality items.")
        return all_results
