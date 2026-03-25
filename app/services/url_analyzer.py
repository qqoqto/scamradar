"""URL analyzer — domain safety, blacklist check, impersonation detection."""

import re
import logging
from urllib.parse import urlparse
from typing import Optional

import httpx

from app.config import get_settings
from app.models.schemas import AnalysisResult
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

# Known official domains (whitelist)
OFFICIAL_DOMAINS = {
    "line.me", "naver.com",
    "instagram.com", "facebook.com", "fb.com", "meta.com",
    "twitter.com", "x.com",
    "threads.net",
    "google.com", "youtube.com", "gmail.com",
    "apple.com", "icloud.com",
    "microsoft.com", "outlook.com", "live.com",
    "gov.tw", "edu.tw",
    "shopee.tw", "shopee.com",
    "momo.com", "momoshop.com.tw",
    "pchome.com.tw", "pcstore.com.tw",
    "books.com.tw", "eslite.com",
    "yahoo.com.tw", "yahoo.com",
    "ruten.com.tw",
    "ettoday.net", "ltn.com.tw", "udn.com", "chinatimes.com",
    "104.com.tw", "1111.com.tw",
}

# Brand impersonation patterns: (regex pattern, real brand name)
IMPERSONATION_PATTERNS = [
    (r"l[i1]ne[-_.]?(event|prize|gift|login|verify|auth)", "LINE"),
    (r"(fb|face[-_.]?book)[-_.]?(login|verify|prize|event)", "Facebook"),
    (r"(ig|insta[-_.]?gram)[-_.]?(verify|login|prize)", "Instagram"),
    (r"(goog[l1]e|g00gle)[-_.]?(login|verify|prize)", "Google"),
    (r"(app[l1]e|iph[o0]ne)[-_.]?(verify|login|id)", "Apple"),
    (r"(shopee|蝦皮)[-_.]?(prize|gift|event|verify)", "Shopee"),
    (r"(momo|富邦)[-_.]?(event|prize|gift)", "Momo"),
    (r"(中華電信|cht|hinet)[-_.]?(verify|login)", "中華電信"),
]

# Known short-URL domains
SHORT_URL_DOMAINS = {"bit.ly", "reurl.cc", "tinyurl.com", "goo.gl", "t.co", "is.gd", "ppt.cc", "lihi.io"}


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return url.lower()


def _is_official(domain: str) -> bool:
    for official in OFFICIAL_DOMAINS:
        if domain == official or domain.endswith(f".{official}"):
            return True
    return False


def _check_impersonation(domain: str) -> Optional[str]:
    for pattern, brand in IMPERSONATION_PATTERNS:
        if re.search(pattern, domain, re.IGNORECASE):
            return brand
    return None


def _is_short_url(domain: str) -> bool:
    return domain in SHORT_URL_DOMAINS


async def _expand_short_url(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
            resp = await client.head(url)
            if resp.status_code in (301, 302, 303, 307, 308):
                return resp.headers.get("location")
    except Exception as e:
        logger.warning(f"Failed to expand short URL {url}: {e}")
    return None


async def _check_google_safe_browsing(url: str) -> bool:
    """Check URL against Google Safe Browsing API. Returns True if dangerous."""
    settings = get_settings()
    if not settings.google_safe_browsing_key:
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={settings.google_safe_browsing_key}",
                json={
                    "client": {"clientId": "scamradar", "clientVersion": "1.0"},
                    "threatInfo": {
                        "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                        "platformTypes": ["ANY_PLATFORM"],
                        "threatEntryTypes": ["URL"],
                        "threatEntries": [{"url": url}],
                    },
                },
            )
            data = resp.json()
            return bool(data.get("matches"))
    except Exception as e:
        logger.warning(f"Google Safe Browsing check failed: {e}")
        return False


def _score_to_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


async def analyze_url(url: str) -> AnalysisResult:
    """Analyze a URL for safety, phishing, and scam indicators."""
    # Normalize
    if not url.startswith("http"):
        url = f"https://{url}"

    domain = _extract_domain(url)

    # Check cache
    cached = await cache_get(f"url:{domain}")
    if cached:
        return AnalysisResult(**cached)

    flags = []
    score = 15  # baseline

    # 1. Official domain check
    if _is_official(domain):
        result = AnalysisResult(
            query_type="url", score=5, level="low",
            flags=["官方網站"],
            explanation=f"這是 {domain} 的官方網站，可以安全訪問。",
            action="這個連結沒問題，可以正常使用。",
            engine="rule",
        )
        await cache_set(f"url:{domain}", result.model_dump(), ttl=7200)
        return result

    # 2. Impersonation check
    impersonated = _check_impersonation(domain)
    if impersonated:
        score += 30
        flags.append(f"疑似偽冒「{impersonated}」的釣魚網站")

    # 3. Short URL expansion
    if _is_short_url(domain):
        flags.append("這是短網址，無法直接看到目的地")
        score += 8
        expanded = await _expand_short_url(url)
        if expanded:
            flags.append(f"短網址指向：{expanded}")
            exp_domain = _extract_domain(expanded)
            exp_impersonated = _check_impersonation(exp_domain)
            if exp_impersonated:
                score += 25
                flags.append(f"展開後疑似偽冒「{exp_impersonated}」")

    # 4. Suspicious TLD
    suspicious_tlds = {".top", ".xyz", ".club", ".buzz", ".work", ".click", ".tk", ".ml", ".ga", ".cf"}
    for tld in suspicious_tlds:
        if domain.endswith(tld):
            score += 12
            flags.append(f"使用高風險域名後綴 ({tld})")
            break

    # 5. Google Safe Browsing
    is_dangerous = await _check_google_safe_browsing(url)
    if is_dangerous:
        score += 35
        flags.append("Google 安全瀏覽偵測為危險網站")

    # 6. LINE-specific domain check
    if "line" in domain and not _is_official(domain):
        if not domain.endswith(".line.me"):
            score += 15
            flags.append("包含「LINE」字樣但不是 .line.me 官方域名")

    score = min(100, score)
    level = _score_to_level(score)

    # Build explanation
    if score < 30:
        explanation = f"網址 {domain} 目前沒有發現明顯的安全問題，不過建議還是留意一下。"
    elif score < 60:
        explanation = f"網址 {domain} 有一些可疑的地方，點擊之前請三思。"
    else:
        explanation = f"網址 {domain} 非常可疑！這很可能是釣魚或詐騙網站。"

    if impersonated:
        explanation += f"\n\n正牌的「{impersonated}」網址不會長這樣。"

    # Build action
    if score < 30:
        action = "可以正常使用，但不要在不熟悉的網站輸入個人資訊。"
    elif score < 60:
        action = "建議不要點擊。如果真的需要，請先從官方管道（例如 Google 搜尋官網）確認。"
    else:
        action = "請不要點擊這個連結！不要輸入任何帳號密碼或個人資訊。如果已經輸入了，請立即更改密碼。"

    result = AnalysisResult(
        query_type="url", score=score, level=level,
        flags=flags, explanation=explanation, action=action,
        engine="rule",
    )

    await cache_set(f"url:{domain}", result.model_dump(), ttl=7200)
    return result
