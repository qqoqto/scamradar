"""Threads profile scraper via ScraperAPI proxy."""

import re
import logging
from typing import Optional
from app.models.schemas import AccountFeatures
from app.scrapers.proxy_client import fetch_page

logger = logging.getLogger(__name__)


async def scrape_threads(username: str) -> Optional[AccountFeatures]:
    username = username.strip().lstrip("@").lower()
    url = f"https://www.threads.net/@{username}"
    resp = await fetch_page(url)
    if not resp or resp.status_code != 200:
        return None
    return _parse_html(username, resp.text)


def _parse_html(username: str, html: str) -> Optional[AccountFeatures]:
    followers, following, bio = 0, 0, ""
    is_verified, has_pic = False, True

    # og:description: "123 Followers on Threads. Bio here..."
    og = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og:
        desc = og.group(1)
        fm = re.search(r'([\d,\.]+[KMkm]?)\s+[Ff]ollowers?', desc)
        if fm:
            followers = _parse_count(fm.group(1))
        bm = re.search(r'[Ff]ollowers?[^.]*\.\s*(.+)', desc)
        if bm:
            bio = bm.group(1).strip()

    # Try JSON embedded data
    fc = re.search(r'"follower_count":\s*(\d+)', html)
    if fc:
        followers = max(followers, int(fc.group(1)))
    fwc = re.search(r'"following_count":\s*(\d+)', html)
    if fwc:
        following = int(fwc.group(1))

    if '"is_verified":true' in html:
        is_verified = True
    if "anonymousUser" in html or "default_profile" in html:
        has_pic = False

    if followers == 0 and not og:
        return None

    return AccountFeatures(
        username=username, platform="threads", followers=followers, following=following,
        post_count=0, has_profile_pic=has_pic, has_bio=bool(bio),
        bio_text=bio[:500], is_verified=is_verified,
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
