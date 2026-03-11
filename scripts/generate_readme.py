"""Generate the README.md from collected use cases."""
from datetime import datetime, timezone
from collections import defaultdict

CATEGORIES_ORDER = [
    "Personal & Productivity",
    "Developer Tools",
    "Business & Automation",
    "Smart Home & IoT",
    "Content & Media",
    "Finance & Trading",
    "Multi-Agent Systems",
]

CATEGORY_SLUGS = {
    "Personal & Productivity": "personal--productivity",
    "Developer Tools": "developer-tools",
    "Business & Automation": "business--automation",
    "Smart Home & IoT": "smart-home--iot",
    "Content & Media": "content--media",
    "Finance & Trading": "finance--trading",
    "Multi-Agent Systems": "multi-agent-systems",
}

CATEGORY_DESCRIPTIONS = {
    "Personal & Productivity": "Use cases for personal task management, daily routines, and productivity workflows.",
    "Developer Tools": "Tools and automations for software development, CI/CD, code review, and DevOps.",
    "Business & Automation": "Business process automation, CRM workflows, customer support, and enterprise use cases.",
    "Smart Home & IoT": "Home automation, IoT device integration, and smart environment control.",
    "Content & Media": "Content creation, social media automation, blog publishing, and media workflows.",
    "Finance & Trading": "Financial tracking, trading automation, expense management, and portfolio monitoring.",
    "Multi-Agent Systems": "Complex multi-agent pipelines, orchestration, and collaborative AI workflows.",
}

SOURCE_LABELS = {
    "awesome-openclaw-usecases": "[awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases)",
    "github-search": "GitHub Search",
}


def source_label(source: str) -> str:
    if source in SOURCE_LABELS:
        return SOURCE_LABELS[source]
    if source.startswith("reddit/"):
        sub = source.split("/", 1)[1]
        return f"[r/{sub}](https://www.reddit.com/r/{sub})"
    if source == "reddit-search":
        return "Reddit Search"
    return source


def anchor(text: str) -> str:
    return text.lower().replace(" ", "-").replace("&", "").replace("/", "").replace("--", "-")


def generate_readme(usecases: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(usecases)

    # Group by category
    by_category = defaultdict(list)
    for uc in usecases:
        cat = uc.get("category", "Personal & Productivity")
        if cat not in CATEGORIES_ORDER:
            cat = "Personal & Productivity"
        by_category[cat].append(uc)

    # Sort each category by title
    for cat in by_category:
        by_category[cat].sort(key=lambda x: x.get("title", "").lower())

    lines = []

    # Header
    lines.append("# OpenClaw Use Cases\n")
    lines.append("> Auto-updated daily collection of real-world OpenClaw use cases gathered from GitHub and Reddit.\n")
    lines.append(f"**[{total} use cases]** · **Last updated: {now}**\n")

    # Table of Contents
    lines.append("## Table of Contents\n")
    for cat in CATEGORIES_ORDER:
        count = len(by_category.get(cat, []))
        slug = CATEGORY_SLUGS.get(cat, anchor(cat))
        lines.append(f"- [{cat}](#{slug}) ({count})")
    lines.append("")

    # Category sections
    for cat in CATEGORIES_ORDER:
        items = by_category.get(cat, [])
        lines.append(f"## {cat}\n")
        lines.append(f"*{CATEGORY_DESCRIPTIONS.get(cat, '')}*\n")

        if not items:
            lines.append("*No use cases collected yet for this category.*\n")
            continue

        for uc in items:
            title = uc.get("title", "Untitled")
            url = uc.get("url", "")
            description = uc.get("description", "")
            src = source_label(uc.get("source", ""))
            date = uc.get("date_added", "")

            if url:
                lines.append(f"### [{title}]({url})\n")
            else:
                lines.append(f"### {title}\n")

            if description:
                lines.append(f"{description}\n")

            meta_parts = []
            if src:
                meta_parts.append(f"**Source:** {src}")
            if date:
                meta_parts.append(f"**Added:** {date}")
            if meta_parts:
                lines.append(" · ".join(meta_parts))

            lines.append("\n---\n")

    # Sources & Credits
    lines.append("## Sources & Credits\n")
    lines.append("This collection is automatically gathered from:\n")
    lines.append("- [awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases) by hesamsheikh")
    lines.append("- GitHub repository search")
    lines.append("- Reddit: [r/openclaw](https://www.reddit.com/r/openclaw), [r/selfhosted](https://www.reddit.com/r/selfhosted), [r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA), [r/AI_Agents](https://www.reddit.com/r/AI_Agents)")
    lines.append("")
    lines.append("---")
    lines.append(f"*Auto-generated on {now} · [Contribute](https://github.com/hesamsheikh/awesome-openclaw-usecases)*")
    lines.append("")

    return "\n".join(lines)
