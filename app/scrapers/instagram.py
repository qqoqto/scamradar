"""Instagram profile scraper via ScraperAPI proxy."""

import re
import json
import logging
from typing import Optional
from app.models.schemas import AccountFeatures
from app.scrapers.proxy_client import fetch_page

logger = logging.getLogger(__name__)


async def scrape_instagram(username: str) -> Optional[AccountFeatures]:
    username = username.strip().lstrip("@").lower()
    # Try profile page first, then mobile API
    for method in [_scrape_profile_page, _scrape_mobile_api]:
        result = await method(username)
        if result:
            return result
    logger.info(f"Instagram: all methods failed for @{username}")
    return None


async def _scrape_profile_page(username: str) -> Optional[AccountFeatures]:
    url = f"https://www.instagram.com/{username}/"
    resp = await fetch_page(url)
    if not resp or resp.status_code != 200:
        return None
    html = resp.text
    if '"LoginAndSignupPage"' in html or "/accounts/login" in html:
        logger.info(f"Instagram @{username}: login wall")
        return None
    return _parse_html(username, html)


async def _scrape_mobile_api(username: str) -> Optional[AccountFeatures]:
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    resp = await fetch_page(url, extra_headers={"X-IG-App-ID": "936619743392459"})
    if not resp or resp.status_code != 200:
        return None
    try:
        user = resp.json().get("data", {}).get("user")
        if not user:
            return None
        return _json_to_features(username, user)
    except Exception:
        return None


def _parse_html(username: str, html: str) -> Optional[AccountFeatures]:
    try:
        # Try _sharedData JSON
        m = re.search(r'window\._sharedData\s*=\s*({.+?});</script>', html, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            user = data.get("entry_data", {}).get("ProfilePage", [{}])[0].get("graphql", {}).get("user", {})
            if user:
                return _json_to_features(username, user)
        # Fallback: meta tags
        return _parse_meta_tags(username, html)
    except Exception as e:
        logger.warning(f"Instagram parse error @{username}: {e}")
        return None


def _parse_meta_tags(username: str, html: str) -> Optional[AccountFeatures]:
    followers, following, posts, bio = 0, 0, 0, ""
    og = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og:
        desc = og.group(1)
        for val, label in re.findall(r'([\d,\.]+[KMkm]?)\s+(Followers?|Following|Posts?)', desc, re.IGNORECASE):
            num = _parse_count(val)
            lb = label.lower()
            if "follower" in lb: followers = num
            elif "following" in lb: following = num
            elif "post" in lb: posts = num
        bm = re.search(r'Posts?\s*[-–—]\s*(.+)', desc)
        if bm:
            bio = bm.group(1).strip()
    if followers == 0 and following == 0 and posts == 0 and not og:
        return None
    return AccountFeatures(
        username=username, platform="instagram", followers=followers, following=following,
        post_count=posts, has_profile_pic="anonymousUser" not in html,
        has_bio=bool(bio), bio_text=bio[:500], is_verified='"is_verified":true' in html,
    )


def _json_to_features(username: str, user: dict) -> AccountFeatures:
    return AccountFeatures(
        username=username, platform="instagram",
        followers=user.get("edge_followed_by", {}).get("count") or user.get("follower_count") or 0,
        following=user.get("edge_follow", {}).get("count") or user.get("following_count") or 0,
        post_count=user.get("edge_owner_to_timeline_media", {}).get("count") or user.get("media_count") or 0,
        has_profile_pic=not user.get("is_default_profile_image", True),
        has_bio=bool((user.get("biography", "") or "").strip()),
        bio_text=(user.get("biography", "") or "")[:500],
        is_verified=user.get("is_verified", False),
    )


def _parse_count(val: str) -> int:
    val = val.strip().replace(",", "")
    m = 1
    if val.upper().endswith("K"): m, val = 1000, val[:-1]
    elif val.upper().endswith("M"): m, val = 1_000_000, val[:-1]
    try:
        return int(float(val) * m)
    except ValueError:
        return 0
