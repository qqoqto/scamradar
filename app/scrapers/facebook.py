"""Facebook profile/page scraper via ScraperAPI proxy."""

import re
import logging
from typing import Optional
from app.models.schemas import AccountFeatures
from app.scrapers.proxy_client import fetch_page

logger = logging.getLogger(__name__)


async def scrape_facebook(username: str) -> Optional[AccountFeatures]:
    username = username.strip().lstrip("@").lower()
    url = f"https://www.facebook.com/{username}"
    resp = await fetch_page(url)
    if not resp or resp.status_code != 200:
        return None
    html = resp.text
    if "/login" in str(resp.url) or "login_form" in html:
        logger.info(f"Facebook @{username}: login wall")
        return None
    return _parse_html(username, html)


def _parse_html(username: str, html: str) -> Optional[AccountFeatures]:
    followers, bio = 0, ""
    is_verified = False

    og = re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]*)"', html)
    if og:
        desc = og.group(1)
        fm = re.search(r'([\d,\.]+[KMkm]?)\s+(?:followers?|追蹤者)', desc, re.IGNORECASE)
        if fm:
            followers = _parse_count(fm.group(1))
        lm = re.search(r'([\d,\.]+[KMkm]?)\s+(?:likes?|讚)', desc, re.IGNORECASE)
        if lm and followers == 0:
            followers = _parse_count(lm.group(1))

    if '"is_verified":true' in html:
        is_verified = True

    if followers == 0 and not og:
        return None

    return AccountFeatures(
        username=username, platform="facebook", followers=followers, following=0,
        post_count=0, has_profile_pic=True, has_bio=bool(bio),
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
