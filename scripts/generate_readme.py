"""Generate a beautiful, curated README from collected use cases."""
from datetime import datetime, timezone
from collections import defaultdict

CATEGORIES = [
    ("🧑‍💻", "Developer Tools",        "CI/CD pipelines, code review, API automation, DevOps workflows."),
    ("⚡", "Personal & Productivity", "Daily briefings, task management, smart scheduling, life automation."),
    ("🏢", "Business & Automation",   "CRM workflows, customer support, sales automation, reporting."),
    ("🤖", "Multi-Agent Systems",     "Orchestration, agent pipelines, crew AI, complex reasoning chains."),
    ("📣", "Content & Media",         "Blog publishing, social media, newsletters, video automation."),
    ("🏠", "Smart Home & IoT",        "Home automation, IoT sensors, device control, environment monitoring."),
    ("💰", "Finance & Trading",       "Portfolio tracking, expense management, trading bots, budgeting."),
]

CATEGORY_NAMES = [c[1] for c in CATEGORIES]

CATEGORY_SLUGS = {
    "Developer Tools":        "developer-tools",
    "Personal & Productivity":"personal--productivity",
    "Business & Automation":  "business--automation",
    "Multi-Agent Systems":    "multi-agent-systems",
    "Content & Media":        "content--media",
    "Smart Home & IoT":       "smart-home--iot",
    "Finance & Trading":      "finance--trading",
}

# Max items shown per category in the README
MAX_PER_CATEGORY = 30

# Titles containing these are discussions/complaints, not use cases
NOISE_TITLE_FRAGMENTS = [
    "am i doing something wrong", "any good reason", "i'm out", "im out",
    "overblown", "lackluster", "leaving", "uninstall", "disappointed",
    "why is openclaw", "openclaw bad", "openclaw dead", "is openclaw worth",
    "alternatives to openclaw", "openclaw vs", "vs openclaw",
]


def is_display_worthy(uc: dict) -> bool:
    """Final quality gate before rendering."""
    src = uc.get("source", "")
    title_lower = uc.get("title", "").lower()

    # Always show curated items
    if src == "awesome-openclaw-usecases":
        return True

    # Filter out noise titles
    if any(f in title_lower for f in NOISE_TITLE_FRAGMENTS):
        return False

    # Reddit: need real engagement
    if src.startswith("reddit/"):
        return uc.get("stars", 0) >= 10

    # GitHub repos: need description and at least 1 star
    if src in ("github", "github-search", "github-code-search"):
        return bool(uc.get("description", "").strip()) and uc.get("stars", 0) >= 1

    return True


def quality_score(uc: dict) -> float:
    """Score used to rank items within a category."""
    score = float(uc.get("stars", 0))
    # Prefer curated / awesome-list sources
    src = uc.get("source", "")
    if src == "awesome-openclaw-usecases":
        score += 1000
    elif src.startswith("reddit/"):
        score += float(uc.get("stars", 0)) * 0.5
    # Prefer items with real descriptions
    if len(uc.get("description", "")) > 50:
        score += 10
    return score


def source_badge(uc: dict) -> str:
    src = uc.get("source", "")
    stars = uc.get("stars", 0)
    if src == "awesome-openclaw-usecases":
        return "⭐ curated"
    if src == "github" or src == "github-code-search":
        return f"★ {stars}" if stars else "GitHub"
    if src.startswith("reddit/"):
        sub = src.split("/", 1)[1]
        return f"r/{sub} · ↑{stars}"
    return src


def generate_readme(usecases: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Filter, group, and rank
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for uc in usecases:
        if not is_display_worthy(uc):
            continue
        cat = uc.get("category", "Personal & Productivity")
        if cat not in CATEGORY_NAMES:
            cat = "Personal & Productivity"
        by_cat[cat].append(uc)

    for cat in by_cat:
        by_cat[cat].sort(key=quality_score, reverse=True)

    total_shown = sum(min(len(by_cat.get(c[1], [])), MAX_PER_CATEGORY) for c in CATEGORIES)
    total_collected = len(usecases)

    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines += [
        "# 🦾 Awesome OpenClaw Use Cases",
        "",
        "> A curated, auto-updated collection of real-world **OpenClaw** use cases — from personal automation to production multi-agent systems.",
        "",
        f"![Use Cases](https://img.shields.io/badge/use%20cases-{total_shown}-blue?style=flat-square)"
        f"  ![Updated](https://img.shields.io/badge/updated-{now}-green?style=flat-square)"
        f"  ![Sources](https://img.shields.io/badge/sources-GitHub%20%2B%20Reddit-orange?style=flat-square)",
        "",
        "**What is OpenClaw?** An open-source AI agent framework for building autonomous workflows.",
        "This repo auto-discovers and curates the best community-built use cases every day.",
        "",
        "---",
        "",
    ]

    # ── Table of Contents ───────────────────────────────────────────────────
    lines += ["## Contents", ""]
    for emoji, cat, _ in CATEGORIES:
        count = min(len(by_cat.get(cat, [])), MAX_PER_CATEGORY)
        slug = CATEGORY_SLUGS[cat]
        lines.append(f"- [{emoji} {cat}](#{slug}) &nbsp; `{count}`")
    lines += [
        "",
        "---",
        "",
    ]

    # ── Category Sections ───────────────────────────────────────────────────
    for emoji, cat, subtitle in CATEGORIES:
        items = by_cat.get(cat, [])[:MAX_PER_CATEGORY]
        lines += [
            f"## {emoji} {cat}",
            "",
            f"*{subtitle}*",
            "",
        ]

        if not items:
            lines += ["*No entries yet — [contribute one!](#contributing)*", "", "---", ""]
            continue

        for uc in items:
            title = uc.get("title", "Untitled").strip()
            url = uc.get("url", "")
            desc = uc.get("description", "").strip()
            badge = source_badge(uc)

            title_part = f"[{title}]({url})" if url else title
            desc_part = f" — {desc}" if desc else ""
            badge_part = f" `{badge}`" if badge else ""

            lines.append(f"- **{title_part}**{desc_part}{badge_part}")

        lines += ["", "---", ""]

    # ── Contributing ────────────────────────────────────────────────────────
    lines += [
        "## Contributing",
        "",
        "Found a great OpenClaw use case that's missing?",
        "",
        "1. **Submit to the source** — open a PR on [awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases) and it'll appear here automatically.",
        "2. **Share on Reddit** — post in [r/openclaw](https://reddit.com/r/openclaw) or [r/OpenClawUseCases](https://reddit.com/r/OpenClawUseCases) with your use case.",
        "",
        "---",
        "",
        "## Sources",
        "",
        "| Source | Description |",
        "|--------|-------------|",
        "| [awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases) | Manually curated collection by hesamsheikh |",
        "| GitHub Search | Repos tagged with openclaw use case / workflow / template |",
        "| Reddit | r/openclaw · r/OpenClawUseCases · r/LocalLLaMA · r/AI_Agents · r/selfhosted |",
        "",
        f"*Auto-updated daily · {total_collected} items collected · {total_shown} curated · Last run: {now}*",
        "",
    ]

    return "\n".join(lines)
