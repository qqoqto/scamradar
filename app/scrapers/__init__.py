"""
ScamRadar — Social media scraper orchestrator.
Tries multiple platforms concurrently, picks best result.
Supports platform hints: "ig:username", "threads:username", etc.
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

PLATFORM_ALIASES = {
    "ig": "instagram", "instagram": "instagram", "insta": "instagram",
    "threads": "threads", "thread": "threads",
    "fb": "facebook", "facebook": "facebook",
    "x": "x", "twitter": "x", "tw": "x",
}

SCRAPERS = {
    "instagram": scrape_instagram,
    "threads": scrape_threads,
    "facebook": scrape_facebook,
    "x": scrape_x,
}


def _detect_platform_hint(username: str) -> tuple[Optional[str], str]:
    """Detect platform hint from 'ig:username' format."""
    if ":" in username and not username.startswith("http"):
        parts = username.split(":", 1)
        hint = parts[0].strip().lower()
        clean = parts[1].strip().lstrip("@")
        if hint in PLATFORM_ALIASES:
            return PLATFORM_ALIASES[hint], clean
    return None, username.strip().lstrip("@")


def _score_features(f: AccountFeatures) -> int:
    """Score how much useful data we got (higher = more data)."""
    score = 0
    if f.followers > 0: score += 3
    if f.following > 0: score += 2
    if f.post_count > 0: score += 2
    if f.bio_text: score += 1
    if f.account_age_days is not None: score += 2
    if f.platform != "unknown": score += 1
    return score


async def scrape_profile(username: str) -> Optional[AccountFeatures]:
    """Main entry: scrape a username across platforms."""
    platform_hint, clean_username = _detect_platform_hint(username)
    if not clean_username:
        return None

    # If platform hint given, try only that platform
    if platform_hint and platform_hint in SCRAPERS:
        logger.info(f"Scraping {platform_hint} for @{clean_username} (hint)")
        result = await SCRAPERS[platform_hint](clean_username)
        if result:
            logger.info(f"✓ {platform_hint} @{clean_username}: {result.followers} followers, {result.post_count} posts")
        return result

    # No hint — try all platforms concurrently
    logger.info(f"Scraping all platforms for @{clean_username}")
    tasks = {p: asyncio.create_task(s(clean_username)) for p, s in SCRAPERS.items()}

    results = {}
    for platform, task in tasks.items():
        try:
            result = await asyncio.wait_for(task, timeout=25)
            if result:
                results[platform] = result
                logger.info(f"✓ {platform} @{clean_username}: {result.followers} followers, {result.post_count} posts")
        except asyncio.TimeoutError:
            logger.warning(f"✗ {platform} @{clean_username}: timeout")
        except Exception as e:
            logger.warning(f"✗ {platform} @{clean_username}: {e}")

    if not results:
        logger.info(f"No platform data found for @{clean_username}")
        return None

    best = max(results.values(), key=_score_features)
    best.cross_platform_count = len(results)
    return best
