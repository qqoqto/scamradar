"""
X (Twitter) profile scraper — lightweight, no browser needed.

Strategy:
1. Try Twitter syndication API (public, no auth needed)
2. Fallback: try Nitter instances (open-source Twitter frontend)
3. If all fail, return None
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

# Public Nitter instances (fallback, may go down)
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]


async def scrape_x(username: str) -> Optional[AccountFeatures]:
    """Scrape X/Twitter public profile."""
    username = username.strip().lstrip("@").lower()

    # Method 1: Twitter syndication API
    features = await _scrape_syndication(username)
    if features:
        return features

    # Method 2: Nitter instances
    features = await _scrape_nitter(username)
    if features:
        return features

    logger.info(f"X/Twitter scrape failed for @{username}")
    return None


async def _scrape_syndication(username: str) -> Optional[AccountFeatures]:
    """Use Twitter's public syndication API."""
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code != 200:
                return None

            html = resp.text

            # Extract embedded JSON data
            data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.+?\})</script>', html, re.DOTALL)
            if not data_match:
                return None

            data = json.loads(data_match.group(1))
            # Navigate the JSON structure to find user info
            props = data.get("props", {}).get("pageProps", {})
            timeline = props.get("timeline", {})

            # Try to extract user from the first entry
            entries = timeline.get("entries", [])
            user_data = None
            for entry in entries:
                content = entry.get("content", {})
                tweet = content.get("tweet", {})
                if tweet.get("user"):
                    user_data = tweet["user"]
                    break

            if not user_data:
                return None

            return AccountFeatures(
                username=username,
                platform="x",
                account_age_days=None,
                followers=user_data.get("followers_count", 0),
                following=user_data.get("friends_count", 0),
                post_count=user_data.get("statuses_count", 0),
                has_profile_pic=not user_data.get("default_profile_image", True),
                has_bio=bool(user_data.get("description", "").strip()),
                bio_text=(user_data.get("description", "") or "")[:500],
                is_verified=user_data.get("verified", False) or user_data.get("is_blue_verified", False),
                engagement_rate=0.0,
                cross_platform_count=0,
                in_blacklist=False,
                report_count=0,
            )

    except Exception as e:
        logger.warning(f"X syndication error for @{username}: {e}")
        return None


async def _scrape_nitter(username: str) -> Optional[AccountFeatures]:
    """Try Nitter instances as fallback."""
    for instance in NITTER_INSTANCES:
        try:
            url = f"{instance}/{username}"
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code != 200:
                    continue

                html = resp.text
                return _parse_nitter_html(username, html)

        except Exception:
            continue

    return None


def _parse_nitter_html(username: str, html: str) -> Optional[AccountFeatures]:
    """Parse Nitter profile page."""
    followers = 0
    following = 0
    posts = 0
    bio = ""
    is_verified = False

    # Nitter shows stats in specific CSS classes
    # <span class="profile-stat-num">1,234</span>
    stat_nums = re.findall(r'class="profile-stat-num"[^>]*>([^<]+)', html)
    stat_labels = re.findall(r'class="profile-stat-header"[^>]*>([^<]+)', html)

    for i, label in enumerate(stat_labels):
        if i < len(stat_nums):
            num = _parse_count(stat_nums[i])
            label_lower = label.lower().strip()
            if "tweet" in label_lower or "post" in label_lower:
                posts = num
            elif "following" in label_lower:
                following = num
            elif "follower" in label_lower:
                followers = num

    # Bio
    bio_match = re.search(r'class="profile-bio"[^>]*>(.+?)</div>', html, re.DOTALL)
    if bio_match:
        bio = re.sub(r'<[^>]+>', '', bio_match.group(1)).strip()

    # Verified
    if "verified-icon" in html or "icon-ok" in html:
        is_verified = True

    if followers == 0 and following == 0 and posts == 0:
        return None

    return AccountFeatures(
        username=username,
        platform="x",
        account_age_days=None,
        followers=followers,
        following=following,
        post_count=posts,
        has_profile_pic=True,
        has_bio=bool(bio),
        bio_text=bio[:500],
        is_verified=is_verified,
        engagement_rate=0.0,
        cross_platform_count=0,
        in_blacklist=False,
        report_count=0,
    )


def _parse_count(val: str) -> int:
    val = val.strip().replace(",", "").replace("\xa0", "")
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
