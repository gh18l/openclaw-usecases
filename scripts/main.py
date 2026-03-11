"""Orchestrator: fetch, merge, persist, and generate README."""
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "usecases.json"
README_FILE = ROOT / "README.md"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))


def load_existing() -> dict[str, dict]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} existing use cases.")
            return {uc["id"]: uc for uc in data if "id" in uc}
        except Exception as e:
            logger.warning(f"Could not load {DATA_FILE}: {e}")
    return {}


def save_usecases(usecases: dict[str, dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    items = sorted(usecases.values(), key=lambda x: x.get("title", "").lower())
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(items)} use cases.")


def merge(existing: dict[str, dict], new_items: list[dict]) -> dict[str, dict]:
    merged = dict(existing)
    added = updated = 0
    for uc in new_items:
        uid = uc.get("id")
        if not uid:
            continue
        if uid in merged:
            original_date = merged[uid].get("date_added")
            merged[uid] = uc
            if original_date:
                merged[uid]["date_added"] = original_date
            updated += 1
        else:
            merged[uid] = uc
            added += 1
    logger.info(f"Merge: +{added} new, ~{updated} updated → {len(merged)} total.")
    return merged


def main() -> None:
    logger.info("=== OpenClaw Use Cases Collector ===")
    existing = load_existing()
    new_items: list[dict] = []

    try:
        from fetch_github import GitHubFetcher
        gh_items = GitHubFetcher().fetch_all()
        new_items.extend(gh_items)
    except Exception as e:
        logger.warning(f"GitHub fetch failed: {e}")

    try:
        from fetch_reddit import RedditFetcher
        rd_items = RedditFetcher().fetch_all()
        new_items.extend(rd_items)
    except Exception as e:
        logger.warning(f"Reddit fetch failed: {e}")

    merged = merge(existing, new_items)
    save_usecases(merged)

    try:
        from generate_readme import generate_readme
        readme = generate_readme(list(merged.values()))
        README_FILE.write_text(readme, encoding="utf-8")
        logger.info(f"README.md written ({len(readme):,} chars).")
    except Exception as e:
        logger.warning(f"README generation failed: {e}")

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()
