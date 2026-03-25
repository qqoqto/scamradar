"""
Instagram profile scraper — lightweight, no browser needed.

Strategy:
1. Try fetching public profile page and parse meta tags / JSON-LD
2. Fallback: try i.instagram.com mobile API endpoint
3. If all fail, return None (caller falls back to heuristics)

Note: Instagram heavily rate-limits and blocks scrapers.
Results are cached aggressively (1 hour) to minimize requests.
"""

import re
import json
import logging
from typing import Optional
import httpx

from app.models.schemas import AccountFeatures

logger = logging.getLogger(__name__)

# Realistic browser headers to avoid instant blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


async def scrape_instagram(username: str) -> Optional[AccountFeatures]:
    """
    Attempt to scrape Instagram public profile.
    Returns AccountFeatures if successful, None if blocked/not found.
    """
    username = username.strip().lstrip("@").lower()

    # Method 1: Public profile page — parse meta tags
    features = await _scrape_profile_page(username)
    if features:
        return features

    # Method 2: Try mobile web API
    features = await _scrape_mobile_api(username)
    if features:
        return features

    logger.info(f"Instagram scrape failed for @{username}, falling back to heuristics")
    return None


async def _scrape_profile_page(username: str) -> Optional[AccountFeatures]:
    """Parse Instagram public profile page for meta info."""
    url = f"https://www.instagram.com/{username}/"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)

            if resp.status_code == 404:
                logger.info(f"Instagram @{username}: 404 not found")
                return None

            if resp.status_code != 200:
                logger.warning(f"Instagram @{username}: HTTP {resp.status_code}")
                return None

            html = resp.text

            # Check if login wall
            if '"LoginAndSignupPage"' in html or "login" in resp.url.path:
                logger.info(f"Instagram @{username}: login wall hit")
                return None

            return _parse_profile_html(username, html)

    except httpx.TimeoutException:
        logger.warning(f"Instagram @{username}: timeout")
        return None
    except Exception as e:
        logger.warning(f"Instagram @{username}: error — {e}")
        return None


def _parse_profile_html(username: str, html: str) -> Optional[AccountFeatures]:
    """Extract profile data from Instagram HTML page."""
    try:
        # Try to find shared_data JSON embedded in page
        # Pattern: window._sharedData = {...};
        shared_match = re.search(r'window\._sharedData\s*=\s*({.+?});</script>', html, re.DOTALL)
        if shared_match:
            data = json.loads(shared_match.group(1))
            user = data.get("entry_data", {}).get("ProfilePage", [{}])[0].get("graphql", {}).get("user", {})
            if user:
                return _user_json_to_features(username, user, "instagram")

        # Try newer pattern: __additionalData or similar
        additional_match = re.search(r'"user":\s*({[^}]{50,}?})\s*[,}]', html)
        if additional_match:
            try:
                user = json.loads(additional_match.group(1))
                if "edge_followed_by" in str(user) or "follower_count" in str(user):
                    return _user_json_to_features(username, user, "instagram")
            except json.JSONDecodeError:
                pass

        # Fallback: parse meta tags
        return _parse_meta_tags(username, html)

    except Exception as e:
        logger.warning(f"Instagram parse error for @{username}: {e}")
        return None


def _parse_meta_tags(username: str, html: str) -> Optional[AccountFeatures]:
    """Extract basic info from <meta> tags."""
    followers = 0
    following = 0
    posts = 0
    has_pic = True
    bio = ""

    # <meta property="og:description" content="1,234 Followers, 567 Following, 89 Posts - ..." />
    og_desc = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og_desc:
        desc = og_desc.group(1)
        # Parse "1,234 Followers, 567 Following, 89 Posts"
        nums = re.findall(r'([\d,\.]+[KMkm]?)\s+(Followers?|Following|Posts?)', desc, re.IGNORECASE)
        for val, label in nums:
            num = _parse_count(val)
            label_lower = label.lower()
            if "follower" in label_lower:
                followers = num
            elif "following" in label_lower:
                following = num
            elif "post" in label_lower:
                posts = num

        # Bio is usually after the dash
        bio_match = re.search(r'Posts?\s*[-–—]\s*(.+)', desc)
        if bio_match:
            bio = bio_match.group(1).strip()

    # Check if profile pic is default
    if "instagram.com/static/images/anonymousUser" in html:
        has_pic = False

    # og:title for display name
    og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', html)

    if followers == 0 and following == 0 and posts == 0 and not og_desc:
        return None  # Couldn't extract anything useful

    return AccountFeatures(
        username=username,
        platform="instagram",
        account_age_days=None,
        followers=followers,
        following=following,
        post_count=posts,
        has_profile_pic=has_pic,
        has_bio=bool(bio),
        bio_text=bio[:500],
        is_verified='"is_verified":true' in html or "verified" in html.lower(),
        engagement_rate=0.0,
        cross_platform_count=0,
        in_blacklist=False,
        report_count=0,
    )


async def _scrape_mobile_api(username: str) -> Optional[AccountFeatures]:
    """Try Instagram mobile web API endpoint."""
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        **HEADERS,
        "X-IG-App-ID": "936619743392459",  # Instagram web app ID (public)
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None

            data = resp.json()
            user = data.get("data", {}).get("user")
            if not user:
                return None

            return _user_json_to_features(username, user, "instagram")

    except Exception as e:
        logger.warning(f"Instagram mobile API error for @{username}: {e}")
        return None


def _user_json_to_features(username: str, user: dict, platform: str) -> AccountFeatures:
    """Convert Instagram JSON user object to AccountFeatures."""
    # Handle different JSON structures
    followers = (
        user.get("edge_followed_by", {}).get("count")
        or user.get("follower_count")
        or 0
    )
    following = (
        user.get("edge_follow", {}).get("count")
        or user.get("following_count")
        or 0
    )
    posts = (
        user.get("edge_owner_to_timeline_media", {}).get("count")
        or user.get("media_count")
        or 0
    )
    bio = user.get("biography", "") or ""
    is_verified = user.get("is_verified", False)
    has_pic = not user.get("is_default_profile_image", True)
    profile_pic = user.get("profile_pic_url", "") or user.get("profile_pic_url_hd", "")
    if profile_pic and "anonymousUser" in profile_pic:
        has_pic = False

    return AccountFeatures(
        username=username,
        platform=platform,
        account_age_days=None,
        followers=followers,
        following=following,
        post_count=posts,
        has_profile_pic=has_pic,
        has_bio=bool(bio.strip()),
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
