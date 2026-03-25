"""
Facebook profile scraper — lightweight, no browser needed.

Facebook public profiles/pages can sometimes be parsed from meta tags.
Most personal profiles are private, so this primarily works for
public pages and business accounts.
"""

import re
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


async def scrape_facebook(username: str) -> Optional[AccountFeatures]:
    """Scrape Facebook public profile/page."""
    username = username.strip().lstrip("@").lower()
    url = f"https://www.facebook.com/{username}"

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)

            if resp.status_code == 404:
                logger.info(f"Facebook @{username}: not found")
                return None

            if resp.status_code != 200:
                logger.warning(f"Facebook @{username}: HTTP {resp.status_code}")
                return None

            html = resp.text

            # Check if login wall
            if "/login" in resp.url.path or "login_form" in html:
                logger.info(f"Facebook @{username}: login wall")
                return None

            return _parse_facebook_html(username, html)

    except httpx.TimeoutException:
        logger.warning(f"Facebook @{username}: timeout")
        return None
    except Exception as e:
        logger.warning(f"Facebook @{username}: error — {e}")
        return None


def _parse_facebook_html(username: str, html: str) -> Optional[AccountFeatures]:
    """Parse Facebook profile/page HTML."""
    followers = 0
    bio = ""
    is_verified = False
    has_pic = True

    # og:description often has likes/followers for pages
    og_desc = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og_desc:
        desc = og_desc.group(1)
        # Pages: "12,345 likes · 678 followers · ..."
        follower_match = re.search(r'([\d,\.]+[KMkm]?)\s+(?:followers?|追蹤者)', desc, re.IGNORECASE)
        if follower_match:
            followers = _parse_count(follower_match.group(1))
        like_match = re.search(r'([\d,\.]+[KMkm]?)\s+(?:likes?|讚)', desc, re.IGNORECASE)
        if like_match and followers == 0:
            followers = _parse_count(like_match.group(1))

    # og:title
    og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', html)

    # Verified
    if '"is_verified":true' in html or "verified" in html:
        is_verified = True

    # Profile type detection
    is_page = '"page"' in html.lower() or "pages_reaction" in html

    # If we couldn't extract anything
    if followers == 0 and not og_desc:
        return None

    return AccountFeatures(
        username=username,
        platform="facebook",
        account_age_days=None,
        followers=followers,
        following=0,
        post_count=0,
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
