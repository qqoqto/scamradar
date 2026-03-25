"""
ScamRadar — Proxy HTTP client via ScraperAPI.

If SCRAPER_API_KEY is set, requests go through ScraperAPI (residential IP).
If not set, falls back to direct httpx request (may be blocked by platforms).
"""

import logging
from typing import Optional
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

SCRAPER_API_BASE = "https://api.scraperapi.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def fetch_page(
    url: str,
    timeout: int = 20,
    render_js: bool = False,
    extra_headers: Optional[dict] = None,
) -> Optional[httpx.Response]:
    """Fetch a URL, routing through ScraperAPI if key is available."""
    settings = get_settings()
    api_key = settings.scraper_api_key

    headers = {**DEFAULT_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    if api_key:
        return await _fetch_via_scraperapi(url, api_key, timeout, render_js, headers)
    else:
        return await _fetch_direct(url, timeout, headers)


async def _fetch_via_scraperapi(
    url: str, api_key: str, timeout: int, render_js: bool, headers: dict,
) -> Optional[httpx.Response]:
    """Route request through ScraperAPI residential proxy."""
    params = {
        "api_key": api_key,
        "url": url,
    }
    if render_js:
        params["render"] = "true"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(SCRAPER_API_BASE, params=params, headers=headers)
            logger.info(f"ScraperAPI [{resp.status_code}] → {url}")
            return resp
    except httpx.TimeoutException:
        logger.warning(f"ScraperAPI timeout → {url}")
        return None
    except Exception as e:
        logger.warning(f"ScraperAPI error → {url}: {e}")
        return None


async def _fetch_direct(url: str, timeout: int, headers: dict) -> Optional[httpx.Response]:
    """Direct request without proxy (fallback)."""
    full_headers = {
        **headers,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=full_headers)
            logger.info(f"Direct [{resp.status_code}] → {url}")
            return resp
    except httpx.TimeoutException:
        logger.warning(f"Direct timeout → {url}")
        return None
    except Exception as e:
        logger.warning(f"Direct error → {url}: {e}")
        return None
