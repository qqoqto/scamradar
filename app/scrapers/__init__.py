"""
ScamRadar Phase 3 — Social media scraper orchestrator.

Coordinates scraping across multiple platforms for a given username.
Strategy:
1. If platform hint is given (e.g. "ig:username"), scrape that platform only
2. Otherwise, try all platforms concurrently
3. Pick the result with the most data (highest confidence)
4. If all fail, return None (caller falls back to heuristics)
"""

import asyncio
import logging
from typing import Optional

from app.models.schemas import AccountFeatures
from app.scrapers.instagram import scrape_instagram
from app.scrapers.threads import scrape_threads
from app.scrapers.facebook import scrape_facebook
from app.scrapers.x_twitter import scrape_x

logger = logging.getLogger(__name__)

# Platform aliases for hint detection
PLATFORM_ALIASES = {
    "ig": "instagram",
    "instagram": "instagram",
    "insta": "instagram",
    "threads": "threads",
    "thread": "threads",
    "fb": "facebook",
    "facebook": "facebook",
    "x": "x",
    "twitter": "x",
    "tw": "x",
}

SCRAPERS = {
    "instagram": scrape_instagram,
    "threads": scrape_threads,
    "facebook": scrape_facebook,
    "x": scrape_x,
}


def _detect_platform_hint(username: str) -> tuple[Optional[str], str]:
    """
    Detect platform hint from username format.
    Supports: "ig:username", "threads:username", "fb:username", "x:username"
    Returns (platform_or_None, clean_username)
    """
    if ":" in username and not username.startswith("http"):
        parts = username.split(":", 1)
        hint = parts[0].strip().lower()
        clean = parts[1].strip().lstrip("@")
        if hint in PLATFORM_ALIASES:
            return PLATFORM_ALIASES[hint], clean

    return None, username.strip().lstrip("@")


def _score_features(f: AccountFeatures) -> int:
    """Score how much useful data we got from scraping (higher = more data)."""
    score = 0
    if f.followers > 0:
        score += 3
    if f.following > 0:
        score += 2
    if f.post_count > 0:
        score += 2
    if f.bio_text:
        score += 1
    if f.account_age_days is not None:
        score += 2
    if f.platform != "unknown":
        score += 1
    return score


async def scrape_profile(username: str) -> Optional[AccountFeatures]:
    """
    Main entry point: try to scrape a username across platforms.

    Args:
        username: The username to look up. Can include platform hint like "ig:username".

    Returns:
        AccountFeatures with real data, or None if all platforms fail.
    """
    platform_hint, clean_username = _detect_platform_hint(username)

    if not clean_username:
        return None

    # If platform hint given, try only that platform
    if platform_hint and platform_hint in SCRAPERS:
        logger.info(f"Scraping {platform_hint} for @{clean_username} (hint)")
        result = await SCRAPERS[platform_hint](clean_username)
        if result:
            logger.info(f"Got {platform_hint} data for @{clean_username}: {result.followers} followers")
        return result

    # No hint — try all platforms concurrently
    logger.info(f"Scraping all platforms for @{clean_username}")

    tasks = {
        platform: asyncio.create_task(scraper(clean_username))
        for platform, scraper in SCRAPERS.items()
    }

    results = {}
    for platform, task in tasks.items():
        try:
            result = await asyncio.wait_for(task, timeout=15)
            if result:
                results[platform] = result
                logger.info(f"Got {platform} data for @{clean_username}: {result.followers} followers")
        except asyncio.TimeoutError:
            logger.warning(f"{platform} scrape timed out for @{clean_username}")
        except Exception as e:
            logger.warning(f"{platform} scrape error for @{clean_username}: {e}")

    if not results:
        logger.info(f"No platform data found for @{clean_username}")
        return None

    # Pick the result with the most data
    best = max(results.values(), key=_score_features)

    # Count cross-platform presence
    best.cross_platform_count = len(results)

    logger.info(f"Best result for @{clean_username}: {best.platform} ({best.followers} followers, {len(results)} platforms)")
    return best
