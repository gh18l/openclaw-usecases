"""Orchestrator: fetch, merge, persist, and generate README."""
import json
import logging
import os
import sys
from pathlib import Path

# Allow running as `python scripts/main.py` from project root
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "usecases.json"
README_FILE = ROOT / "README.md"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_existing() -> dict[str, dict]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} existing use cases from {DATA_FILE}")
            return {uc["id"]: uc for uc in data if "id" in uc}
        except Exception as e:
            logger.warning(f"Could not load {DATA_FILE}: {e}")
    return {}


def save_usecases(usecases: dict[str, dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    items = sorted(usecases.values(), key=lambda x: x.get("title", "").lower())
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(items)} use cases to {DATA_FILE}")


def merge(existing: dict[str, dict], new_items: list[dict]) -> dict[str, dict]:
    merged = dict(existing)
    added = 0
    updated = 0
    for uc in new_items:
        uid = uc.get("id")
        if not uid:
            continue
        if uid in merged:
            # Preserve original date_added, update everything else
            original_date = merged[uid].get("date_added")
            merged[uid] = uc
            if original_date:
                merged[uid]["date_added"] = original_date
            updated += 1
        else:
            merged[uid] = uc
            added += 1
    logger.info(f"Merge: {added} new, {updated} updated, {len(merged)} total.")
    return merged


def main() -> None:
    logger.info("=== OpenClaw Use Cases Collector ===")

    existing = load_existing()
    new_items: list[dict] = []

    # --- GitHub ---
    try:
        from fetch_github import GitHubFetcher
        logger.info("Fetching from GitHub...")
        gh = GitHubFetcher()
        gh_items = gh.fetch_all()
        new_items.extend(gh_items)
        logger.info(f"GitHub: {len(gh_items)} items fetched.")
    except Exception as e:
        logger.warning(f"GitHub fetch failed: {e}")

    # --- Reddit ---
    try:
        from fetch_reddit import RedditFetcher
        logger.info("Fetching from Reddit...")
        rd = RedditFetcher()
        rd_items = rd.fetch_all()
        new_items.extend(rd_items)
        logger.info(f"Reddit: {len(rd_items)} items fetched.")
    except Exception as e:
        logger.warning(f"Reddit fetch failed: {e}")

    # --- Merge & persist ---
    merged = merge(existing, new_items)
    save_usecases(merged)

    # --- Generate README ---
    try:
        from generate_readme import generate_readme
        readme = generate_readme(list(merged.values()))
        README_FILE.write_text(readme, encoding="utf-8")
        logger.info(f"README.md written ({len(readme)} chars, {len(merged)} use cases).")
    except Exception as e:
        logger.warning(f"README generation failed: {e}")

    logger.info("=== Done ===")


if __name__ == "__main__":
    # Add scripts dir to path so sibling imports work
    sys.path.insert(0, str(Path(__file__).parent))
    main()
