"""Generate a high-star-worthy README from collected use cases."""
from datetime import datetime, timezone, timedelta
from collections import defaultdict

CATEGORIES = [
    ("⚡", "Personal & Productivity", "Daily briefings, task management, smart scheduling, life automation."),
    ("🧑‍💻", "Developer Tools",        "CI/CD pipelines, code review, API automation, DevOps workflows."),
    ("🤖", "Multi-Agent Systems",     "Orchestration, agent pipelines, crew AI, complex reasoning chains."),
    ("🏢", "Business & Automation",   "CRM workflows, customer support, sales automation, reporting."),
    ("📣", "Content & Media",         "Blog publishing, social media, newsletters, video automation."),
    ("💰", "Finance & Trading",       "Portfolio tracking, expense management, trading bots, budgeting."),
    ("🏠", "Smart Home & IoT",        "Home automation, IoT sensors, device control, environment monitoring."),
]

CATEGORY_NAMES = [c[1] for c in CATEGORIES]

CATEGORY_SLUGS = {
    "Personal & Productivity": "personal--productivity",
    "Developer Tools":         "developer-tools",
    "Multi-Agent Systems":     "multi-agent-systems",
    "Business & Automation":   "business--automation",
    "Content & Media":         "content--media",
    "Finance & Trading":       "finance--trading",
    "Smart Home & IoT":        "smart-home--iot",
}

MAX_PER_CATEGORY = 30
FEATURED_COUNT = 5

NOISE_TITLE_FRAGMENTS = [
    "am i doing something wrong", "any good reason", "i'm out", "im out",
    "overblown", "lackluster", "leaving", "uninstall", "disappointed",
    "why is openclaw", "openclaw bad", "openclaw dead", "is openclaw worth",
    "alternatives to openclaw", "openclaw vs", "vs openclaw",
]


def is_display_worthy(uc: dict) -> bool:
    src = uc.get("source", "")
    title_lower = uc.get("title", "").lower()
    if src == "awesome-openclaw-usecases":
        return True
    if any(f in title_lower for f in NOISE_TITLE_FRAGMENTS):
        return False
    if src.startswith("reddit/"):
        return uc.get("stars", 0) >= 10
    if src in ("github", "github-search", "github-code-search"):
        return bool(uc.get("description", "").strip()) and uc.get("stars", 0) >= 1
    return True


def quality_score(uc: dict) -> float:
    score = float(uc.get("stars", 0))
    src = uc.get("source", "")
    if src == "awesome-openclaw-usecases":
        score += 1000
    elif src.startswith("reddit/"):
        score += float(uc.get("stars", 0)) * 0.5
    if len(uc.get("description", "")) > 60:
        score += 10
    return score


def is_new(uc: dict, days: int = 7) -> bool:
    date_str = uc.get("date_added", "")
    if not date_str:
        return False
    try:
        added = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - added) <= timedelta(days=days)
    except ValueError:
        return False


def truncate(text: str, max_chars: int = 160) -> str:
    if len(text) <= max_chars:
        return text
    # Cut at last space before limit
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:—-") + "…"


def fmt_item(uc: dict, show_source: bool = True) -> str:
    title = uc.get("title", "Untitled").strip()
    url = uc.get("url", "")
    desc = truncate(uc.get("description", "").strip())
    src = uc.get("source", "")
    stars = uc.get("stars", 0)

    title_part = f"[{title}]({url})" if url else title

    if src == "awesome-openclaw-usecases":
        src_label = "⭐ curated"
    elif src.startswith("reddit/"):
        sub = src.split("/", 1)[1]
        src_label = f"[r/{sub}](https://reddit.com/r/{sub}) · ↑{stars}"
    elif src in ("github", "github-search", "github-code-search"):
        src_label = f"★ {stars}" if stars else "GitHub"
    else:
        src_label = src

    desc_part = f" — {desc}" if desc else ""
    src_part = f" `{src_label}`" if show_source else ""

    return f"- **{title_part}**{desc_part}{src_part}"


def generate_readme(usecases: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Filter & group
    worthy = [uc for uc in usecases if is_display_worthy(uc)]
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for uc in worthy:
        cat = uc.get("category", "Personal & Productivity")
        if cat not in CATEGORY_NAMES:
            cat = "Personal & Productivity"
        by_cat[cat].append(uc)
    for cat in by_cat:
        by_cat[cat].sort(key=quality_score, reverse=True)

    total_shown = sum(min(len(by_cat.get(c[1], [])), MAX_PER_CATEGORY) for c in CATEGORIES)
    total_collected = len(usecases)

    # Featured: top picks by quality score
    all_worthy_sorted = sorted(worthy, key=quality_score, reverse=True)
    featured = all_worthy_sorted[:FEATURED_COUNT]

    # New this week
    new_items = [uc for uc in worthy if is_new(uc, days=7)]
    new_items.sort(key=quality_score, reverse=True)

    lines = []

    # ── Hero ────────────────────────────────────────────────────────────────
    lines += [
        "# 🦾 Awesome OpenClaw Use Cases",
        "",
        "> **OpenClaw crossed 100k GitHub stars.** Most people still don't know what to *actually build* with it.",
        "> This repo auto-collects the best real-world use cases from across GitHub and Reddit — updated every day.",
        "",
        (
            f"[![Use Cases](https://img.shields.io/badge/use%20cases-{total_shown}%20curated-blue?style=flat-square)]"
            f"(#contents)"
            f"&nbsp;[![Auto Updated](https://img.shields.io/badge/auto%20updated-daily-brightgreen?style=flat-square)]"
            f"(#sources)"
            f"&nbsp;[![Sources](https://img.shields.io/badge/sources-GitHub%20%2B%20Reddit-orange?style=flat-square)]"
            f"(#sources)"
            f"&nbsp;[![Awesome](https://img.shields.io/badge/awesome-list-fc60a8?style=flat-square&logo=awesomelists)]"
            f"(https://github.com/hesamsheikh/awesome-openclaw-usecases)"
        ),
        "",
        "**How it works:** A GitHub Action runs every morning, scrapes GitHub repos and Reddit posts,",
        "filters for quality, and commits an updated README — so you're always seeing the freshest use cases.",
        "",
        "---",
        "",
    ]

    # ── Featured ────────────────────────────────────────────────────────────
    if featured:
        lines += ["## ✨ Featured", ""]
        lines += ["*Hand-picked from the community's most loved use cases:*", ""]
        for uc in featured:
            lines.append(fmt_item(uc))
        lines += ["", "---", ""]

    # ── New This Week ────────────────────────────────────────────────────────
    if new_items:
        lines += [f"## 🆕 New This Week", ""]
        for uc in new_items[:8]:
            lines.append(fmt_item(uc))
        lines += ["", "---", ""]

    # ── Contents ────────────────────────────────────────────────────────────
    lines += ["## Contents", ""]
    for emoji, cat, _ in CATEGORIES:
        count = min(len(by_cat.get(cat, [])), MAX_PER_CATEGORY)
        slug = CATEGORY_SLUGS[cat]
        lines.append(f"- [{emoji} {cat}](#{slug}) ({count})")
    lines += ["", "---", ""]

    # ── Categories ──────────────────────────────────────────────────────────
    for emoji, cat, subtitle in CATEGORIES:
        items = by_cat.get(cat, [])[:MAX_PER_CATEGORY]
        lines += [f"## {emoji} {cat}", "", f"*{subtitle}*", ""]
        if not items:
            lines += ["*Nothing here yet — [add the first one!](#contributing)*", "", "---", ""]
            continue
        for uc in items:
            lines.append(fmt_item(uc))
        lines += ["", "---", ""]

    # ── Contributing ────────────────────────────────────────────────────────
    lines += [
        "## 🤝 Contributing",
        "",
        "This list is **auto-generated**, but the sources are human-curated.",
        "The easiest way to add a use case:",
        "",
        "| Method | How |",
        "|--------|-----|",
        "| GitHub PR | Open a PR on [awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases) — it auto-appears here within 24h |",
        "| Reddit | Post your use case in [r/openclaw](https://reddit.com/r/openclaw) or [r/OpenClawUseCases](https://reddit.com/r/OpenClawUseCases) |",
        "",
        "> 💡 **Tip:** Posts with 10+ upvotes on Reddit get auto-included here.",
        "",
        "---",
        "",
    ]

    # ── Sources ─────────────────────────────────────────────────────────────
    lines += [
        "## Sources",
        "",
        "| Source | What we pull |",
        "|--------|-------------|",
        "| [awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases) | All verified, manually curated use cases |",
        "| GitHub Search | Repos tagged as openclaw use case / workflow / example / template (⭐1+ only) |",
        "| Reddit | r/openclaw, r/OpenClawUseCases, r/LocalLLaMA, r/AI_Agents, r/selfhosted (↑10+ only) |",
        "",
        "---",
        "",
        f"<sub>🤖 Auto-generated · {total_collected} items collected · {total_shown} displayed · Last updated {now}</sub>",
        "",
    ]

    return "\n".join(lines)
