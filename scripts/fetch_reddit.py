"""Fetch OpenClaw use cases from Reddit using the public JSON API."""
import re
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Broad keyword filter — keep nearly everything openclaw-related
USECASE_KEYWORDS = [
    "use case", "workflow", "setup", "built", "automating", "automated",
    "i built", "i made", "i created", "i wrote", "sharing my", "my setup",
    "how i", "using openclaw", "openclaw to", "with openclaw",
    "openclaw for", "openclaw +", "openclaw -", "running openclaw",
    "deployed", "integration", "automate", "agent", "pipeline",
    "tutorial", "guide", "example", "showcase", "demo", "project",
    "self-hosted", "selfhosted", "docker", "homelab", "n8n",
]

# Subreddits to scrape top posts from
TOP_SUBREDDITS = [
    ("openclaw", 500),
    ("selfhosted", 100),
    ("LocalLLaMA", 100),
    ("AI_Agents", 100),
    ("homeautomation", 50),
    ("MachineLearning", 50),
    ("ChatGPT", 50),
    ("ArtificialIntelligence", 50),
    ("n8n", 100),
    ("learnmachinelearning", 25),
    ("OpenClawUseCases", 500),
]

# (query, subreddit or None for global search)
SEARCH_QUERIES = [
    ("openclaw use case", None),
    ("openclaw workflow", None),
    ("openclaw automation", None),
    ("openclaw agent", None),
    ("openclaw integration", None),
    ("openclaw tutorial", None),
    ("openclaw project", None),
    ("openclaw self-hosted", None),
    ("openclaw docker", None),
    ("openclaw", "selfhosted"),
    ("openclaw", "LocalLLaMA"),
    ("openclaw", "AI_Agents"),
    ("openclaw", "homeautomation"),
    ("openclaw", "n8n"),
    ("openclaw", "ChatGPT"),
    ("openclaw", "MachineLearning"),
    ("openclaw", "ArtificialIntelligence"),
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


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for category, keywords in CATEGORIES_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return "Personal & Productivity"


def make_id(url: str) -> str:
    return re.sub(r"[^a-z0-9]", "-", url.lower())[:80]


def is_usecase_post(title: str, selftext: str) -> bool:
    """Keep posts that mention openclaw + at least one use-case signal."""
    combined = (title + " " + selftext).lower()
    if "openclaw" not in combined:
        return False
    # Accept if it has any use-case keyword, OR is from r/openclaw (always relevant)
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
                logger.warning(f"Reddit {resp.status_code} for {url} — skipping.")
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Reddit request failed for {url}: {e}")
            return None

    def _parse_posts(self, data: dict, source_label: str, min_score: int = 1) -> list[dict]:
        results = []
        posts = data.get("data", {}).get("children", [])
        for post in posts:
            p = post.get("data", {})
            title = p.get("title", "").strip()
            selftext = p.get("selftext", "") or ""
            score = p.get("score", 0)
            permalink = p.get("permalink", "")
            subreddit = p.get("subreddit", "")

            if score < min_score:
                continue
            if not permalink:
                continue
            if not is_usecase_post(title, selftext):
                continue

            url = f"https://www.reddit.com{permalink}"
            description = selftext.strip()[:400] if selftext.strip() else title
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

    def fetch_subreddit_top_paginated(self, subreddit: str, target: int = 500) -> list[dict]:
        """Fetch top posts from a subreddit with pagination via 'after' token."""
        results = []
        seen_ids = set()
        after = None
        fetched = 0

        while fetched < target:
            batch = min(100, target - fetched)
            params = {"limit": batch, "t": "all"}
            if after:
                params["after"] = after

            url = f"{self.BASE_URL}/r/{subreddit}/top.json"
            data = self._get(url, params)
            if not data:
                break

            posts_data = data.get("data", {})
            children = posts_data.get("children", [])
            if not children:
                break

            parsed = self._parse_posts(data, f"reddit/{subreddit}", min_score=1)
            for p in parsed:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    results.append(p)

            after = posts_data.get("after")
            fetched += len(children)

            logger.info(f"  r/{subreddit} top: fetched {fetched}, got {len(results)} use case posts so far")

            if not after or len(children) < batch:
                break

            time.sleep(2)

        logger.info(f"r/{subreddit} top (paginated): {len(results)} use case posts total.")
        return results

    def fetch_search_paginated(self, query: str, subreddit: str = None, target: int = 250) -> list[dict]:
        """Search Reddit with pagination via 'after' token."""
        results = []
        seen_ids = set()
        after = None
        fetched = 0

        while fetched < target:
            batch = min(100, target - fetched)
            if subreddit:
                url = f"{self.BASE_URL}/r/{subreddit}/search.json"
                params = {"q": query, "restrict_sr": "1", "sort": "top", "t": "all", "limit": batch}
            else:
                url = f"{self.BASE_URL}/search.json"
                params = {"q": query, "sort": "top", "t": "all", "limit": batch}
            if after:
                params["after"] = after

            data = self._get(url, params)
            if not data:
                break

            posts_data = data.get("data", {})
            children = posts_data.get("children", [])
            if not children:
                break

            label = f"reddit/{subreddit}" if subreddit else "reddit-search"
            parsed = self._parse_posts(data, label, min_score=1)
            for p in parsed:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    results.append(p)

            after = posts_data.get("after")
            fetched += len(children)

            if not after or len(children) < batch:
                break

            time.sleep(2)

        label = f"r/{subreddit}" if subreddit else "global"
        logger.info(f"Reddit search '{query}' ({label}): {len(results)} use case posts total.")
        return results

    def fetch_all(self) -> list[dict]:
        all_results = []
        seen_ids = set()

        def add_deduped(items):
            for item in items:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    all_results.append(item)

        # Top posts from each subreddit (paginated)
        for subreddit, target in TOP_SUBREDDITS:
            add_deduped(self.fetch_subreddit_top_paginated(subreddit, target=target))
            time.sleep(2)

        # Searches (paginated)
        for query, subreddit in SEARCH_QUERIES:
            add_deduped(self.fetch_search_paginated(query, subreddit, target=250))
            time.sleep(2)

        logger.info(f"Reddit total (deduplicated): {len(all_results)} items.")
        return all_results
