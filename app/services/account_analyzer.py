"""Account analyzer — cross-platform profile lookup + risk scoring.

Phase 3: Now integrates real social media scrapers (Instagram, Threads,
Facebook, X/Twitter) via lightweight httpx-based scraping. Falls back
to heuristic-only analysis if scraping fails.
"""

import re
import logging
from typing import Optional

from app.models.schemas import AnalysisResult, AccountFeatures
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)


# ============================================================
# Risk scoring algorithm
# ============================================================

def score_account(f: AccountFeatures) -> int:
    """Calculate risk score (0–100) from account features."""
    score = 30  # baseline

    # --- Account age ---
    if f.account_age_days is not None:
        if f.account_age_days < 7:
            score += 25
        elif f.account_age_days < 30:
            score += 15
        elif f.account_age_days < 90:
            score += 8

    # --- Follower / following ratio ---
    ratio = f.followers / max(f.following, 1)
    if f.following > 500 and ratio < 0.01:
        score += 20
    elif f.following > 100 and ratio < 0.05:
        score += 12
    elif ratio > 100 and f.followers > 10000:
        score += 8  # possibly bought followers

    # --- Profile completeness ---
    if not f.has_profile_pic:
        score += 12
    if not f.has_bio:
        score += 8
    if f.is_verified:
        score -= 35

    # --- Username analysis ---
    if _has_excessive_numbers(f.username):
        score += 10
    if _has_random_pattern(f.username):
        score += 8

    # --- Content signals ---
    if f.post_count == 0:
        score += 10
    elif f.post_count < 3 and f.followers > 500:
        score += 15

    if f.engagement_rate < 0.5 and f.followers > 100:
        score += 8

    # --- Cross-platform presence ---
    if f.cross_platform_count == 0:
        score += 5
    elif f.cross_platform_count >= 3:
        score -= 10

    # --- Blacklist ---
    if f.in_blacklist:
        score += 30
    if f.report_count > 0:
        score += min(f.report_count * 5, 20)

    # --- Phase 3: Bonus for scraped real data ---
    # If we actually have real follower data, we can be more confident
    if f.platform != "unknown" and f.followers > 0:
        # Real account with real followers → lower baseline
        if f.followers > 1000 and f.post_count > 10:
            score -= 10
        elif f.followers > 100 and f.post_count > 5:
            score -= 5

    return max(0, min(100, score))


def _has_excessive_numbers(username: str) -> bool:
    digits = sum(c.isdigit() for c in username)
    return digits >= 4 and digits / max(len(username), 1) > 0.35


def _has_random_pattern(username: str) -> bool:
    clean = re.sub(r"[_.\-]", "", username.lower())
    if len(clean) < 6:
        return False
    # Check for consonant clusters without vowels (sign of random generation)
    vowels = set("aeiou")
    max_consonant_run = 0
    run = 0
    for c in clean:
        if c.isalpha() and c not in vowels:
            run += 1
            max_consonant_run = max(max_consonant_run, run)
        else:
            run = 0
    return max_consonant_run >= 5


# ============================================================
# Profile lookup — Phase 3: integrated with scrapers
# ============================================================

async def _lookup_profile(username: str) -> AccountFeatures:
    """Look up a username across platforms.

    Phase 3: Tries real scrapers first, falls back to heuristics.
    Supports platform hints: "ig:username", "threads:username", etc.
    """
    try:
        from app.scrapers import scrape_profile
        scraped = await scrape_profile(username)
        if scraped:
            logger.info(f"Scraped real data for @{username}: platform={scraped.platform}, followers={scraped.followers}")
            return scraped
    except Exception as e:
        logger.warning(f"Scraper error for @{username}: {e}")

    # Fallback: heuristic-only features
    logger.info(f"Using heuristic-only analysis for @{username}")
    clean = username.strip().lstrip("@＠")
    # Remove platform hint if present
    if ":" in clean and not clean.startswith("http"):
        clean = clean.split(":", 1)[-1].strip()

    return AccountFeatures(
        username=clean,
        platform="unknown",
        account_age_days=None,
        followers=0,
        following=0,
        post_count=0,
        has_profile_pic=True,  # assume true until scraped
        has_bio=True,
        is_verified=False,
        engagement_rate=0.0,
        cross_platform_count=0,
        in_blacklist=False,
        report_count=0,
    )


def _build_account_explanation(score: int, features: AccountFeatures) -> str:
    """Build human-readable explanation in Traditional Chinese."""
    parts = []
    platform_label = _platform_label(features.platform)

    if score < 30:
        parts.append(f"帳號 @{features.username} 目前看起來沒有明顯的可疑特徵。")
    elif score < 60:
        parts.append(f"帳號 @{features.username} 有一些需要留意的地方：")
    else:
        parts.append(f"帳號 @{features.username} 有多項可疑特徵：")

    # Show data source
    if features.platform != "unknown":
        parts.append(f"（已從 {platform_label} 取得真實資料）")

    if features.account_age_days is not None and features.account_age_days < 30:
        parts.append(f"• 帳號才建立 {features.account_age_days} 天，非常新")
    if not features.has_profile_pic:
        parts.append("• 沒有設定頭像照片")
    if not features.has_bio:
        parts.append("• 沒有填寫個人簡介")
    if features.following > 500 and features.followers < 20:
        parts.append(f"• 追蹤了 {features.following} 人但只有 {features.followers} 個粉絲，比例非常異常")
    if features.post_count == 0 and features.platform != "unknown":
        parts.append("• 完全沒有發過貼文")
    elif features.post_count == 0 and features.platform == "unknown":
        parts.append("• 無法取得貼文資料")
    if _has_excessive_numbers(features.username):
        parts.append("• 帳號名稱含大量數字，疑似自動產生")
    if features.is_verified:
        parts.append("• 已通過官方認證 ✓")
    if features.cross_platform_count >= 2:
        parts.append(f"• 在 {features.cross_platform_count} 個平台上都有找到此帳號")

    return "\n".join(parts)


def _build_account_flags(features: AccountFeatures) -> list[str]:
    flags = []
    if features.platform != "unknown":
        flags.append(f"來源：{_platform_label(features.platform)}")
    if features.account_age_days is not None and features.account_age_days < 30:
        flags.append(f"帳號僅建立 {features.account_age_days} 天")
    if not features.has_profile_pic:
        flags.append("沒有頭像")
    if not features.has_bio:
        flags.append("沒有個人簡介")
    if _has_excessive_numbers(features.username):
        flags.append("帳號名含大量數字")
    if _has_random_pattern(features.username):
        flags.append("帳號名疑似隨機產生")
    if features.following > 500 and features.followers < 20:
        flags.append("追蹤/粉絲比例極度異常")
    if features.post_count == 0 and features.platform != "unknown":
        flags.append("沒有任何貼文")
    if features.in_blacklist:
        flags.append("已被其他使用者回報為詐騙")
    if features.is_verified:
        flags.append("已通過官方認證")
    if features.cross_platform_count >= 2:
        flags.append(f"跨 {features.cross_platform_count} 平台存在")
    return flags


def _platform_label(platform: str) -> str:
    labels = {
        "instagram": "Instagram",
        "threads": "Threads",
        "facebook": "Facebook",
        "x": "X (Twitter)",
        "unknown": "未知",
    }
    return labels.get(platform, platform)


def _score_to_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _build_account_action(score: int) -> str:
    if score < 30:
        return "看起來沒什麼問題，可以正常互動。"
    if score < 60:
        return "建議先觀察一陣子，不要提供個人資訊或匯款。如果對方要求加其他通訊軟體或談錢，就要特別小心。"
    if score < 80:
        return "建議不要互動，可以封鎖對方。如果對方已經聯繫你談投資或感情，很可能是詐騙。"
    return "非常可疑！請立即封鎖並檢舉這個帳號。如果已有金錢損失，請撥打 165 反詐騙專線報案。"


# ============================================================
# Main entry point
# ============================================================

async def analyze_account(username: str) -> AnalysisResult:
    """Analyze a social media account and return risk assessment."""
    clean = username.strip().lstrip("@＠")

    # For cache key, use the full input (with platform hint if any)
    cache_key = f"account:{clean}"
    cached = await cache_get(cache_key)
    if cached:
        return AnalysisResult(**cached)

    # Lookup profile features (tries scrapers → falls back to heuristics)
    features = await _lookup_profile(username)

    # Score
    score = score_account(features)
    level = _score_to_level(score)
    flags = _build_account_flags(features)
    explanation = _build_account_explanation(score, features)
    action = _build_account_action(score)

    # Determine engine type
    engine = "rule"
    if features.platform != "unknown":
        engine = "scraper+rule"

    result = AnalysisResult(
        query_type="account",
        score=score,
        level=level,
        flags=flags,
        explanation=explanation,
        action=action,
        details=features.model_dump(),
        engine=engine,
    )

    # Cache result
    await cache_set(cache_key, result.model_dump(), ttl=3600)

    return result
