"""
Threads profile scraper — lightweight, no browser needed.

Threads (threads.net) by Meta shares the same backend as Instagram.
Public profiles can be accessed at threads.net/@username.
"""

import re
import json
import logging
from typing import Optional
import httpx

from app.models.schemas import AccountFeatures

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def scrape_threads(username: str) -> Optional[AccountFeatures]:
    """Scrape Threads public profile."""
    username = username.strip().lstrip("@").lower()
    url = f"https://www.threads.net/@{username}"

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)

            if resp.status_code == 404:
                logger.info(f"Threads @{username}: not found")
                return None

            if resp.status_code != 200:
                logger.warning(f"Threads @{username}: HTTP {resp.status_code}")
                return None

            html = resp.text
            return _parse_threads_html(username, html)

    except httpx.TimeoutException:
        logger.warning(f"Threads @{username}: timeout")
        return None
    except Exception as e:
        logger.warning(f"Threads @{username}: error — {e}")
        return None


def _parse_threads_html(username: str, html: str) -> Optional[AccountFeatures]:
    """Parse Threads profile HTML for user data."""
    followers = 0
    bio = ""
    is_verified = False
    has_pic = True

    # Try og:description: "123 Followers on Threads. Bio text here..."
    og_desc = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og_desc:
        desc = og_desc.group(1)
        follower_match = re.search(r'([\d,\.]+[KMkm]?)\s+[Ff]ollowers?', desc)
        if follower_match:
            followers = _parse_count(follower_match.group(1))
        # Bio after the follower count
        bio_match = re.search(r'[Ff]ollowers?[^.]*\.\s*(.+)', desc)
        if bio_match:
            bio = bio_match.group(1).strip()

    # og:title for display name
    og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', html)

    # Verified badge
    if '"is_verified":true' in html or "verified" in html.lower():
        is_verified = True

    # Default profile pic check
    if "anonymousUser" in html or "default_profile" in html:
        has_pic = False

    # Try to find JSON data embedded in page
    json_match = re.search(r'"follower_count":\s*(\d+)', html)
    if json_match:
        followers = max(followers, int(json_match.group(1)))

    following_match = re.search(r'"following_count":\s*(\d+)', html)
    following = int(following_match.group(1)) if following_match else 0

    # If we couldn't extract anything meaningful
    if followers == 0 and not og_desc:
        return None

    return AccountFeatures(
        username=username,
        platform="threads",
        account_age_days=None,
        followers=followers,
        following=following,
        post_count=0,  # Threads doesn't easily expose post count in meta
        has_profile_pic=has_pic,
        has_bio=bool(bio),
        bio_text=bio[:500],
        is_verified=is_verified,
        engagement_rate=0.0,
        cross_platform_count=0,
        in_blacklist=False,
        report_count=0,
    )


def _parse_count(val: str) -> int:
    """Parse count strings like '1,234', '12.5K', '1.2M'."""
    val = val.strip().replace(",", "")
    multiplier = 1
    if val.upper().endswith("K"):
        multiplier = 1000
        val = val[:-1]
    elif val.upper().endswith("M"):
        multiplier = 1_000_000
        val = val[:-1]
    try:
        return int(float(val) * multiplier)
    except ValueError:
        return 0
