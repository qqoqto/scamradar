"""X (Twitter) profile scraper via ScraperAPI proxy."""

import re
import json
import logging
from typing import Optional
from app.models.schemas import AccountFeatures
from app.scrapers.proxy_client import fetch_page

logger = logging.getLogger(__name__)


async def scrape_x(username: str) -> Optional[AccountFeatures]:
    username = username.strip().lstrip("@").lower()
    # Try syndication API first
    result = await _scrape_syndication(username)
    if result:
        return result
    # Try profile page via proxy
    result = await _scrape_profile_page(username)
    return result


async def _scrape_syndication(username: str) -> Optional[AccountFeatures]:
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    resp = await fetch_page(url)
    if not resp or resp.status_code != 200:
        return None
    try:
        html = resp.text
        dm = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.+?\})</script>', html, re.DOTALL)
        if not dm:
            return None
        data = json.loads(dm.group(1))
        entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
        for entry in entries:
            user = entry.get("content", {}).get("tweet", {}).get("user")
            if user:
                return AccountFeatures(
                    username=username, platform="x",
                    followers=user.get("followers_count", 0),
                    following=user.get("friends_count", 0),
                    post_count=user.get("statuses_count", 0),
                    has_profile_pic=not user.get("default_profile_image", True),
                    has_bio=bool((user.get("description", "") or "").strip()),
                    bio_text=(user.get("description", "") or "")[:500],
                    is_verified=user.get("verified", False) or user.get("is_blue_verified", False),
                )
    except Exception as e:
        logger.warning(f"X syndication parse error @{username}: {e}")
    return None


async def _scrape_profile_page(username: str) -> Optional[AccountFeatures]:
    url = f"https://x.com/{username}"
    resp = await fetch_page(url, render_js=True)
    if not resp or resp.status_code != 200:
        return None
    html = resp.text
    # Try to extract from meta tags
    followers = 0
    og = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og:
        desc = og.group(1)
        fm = re.search(r'([\d,\.]+[KMkm]?)\s+[Ff]ollowers?', desc)
        if fm:
            followers = _parse_count(fm.group(1))
    if followers == 0:
        return None
    return AccountFeatures(
        username=username, platform="x", followers=followers,
        has_profile_pic=True, has_bio=bool(og),
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
