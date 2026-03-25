"""Phone number analyzer — Taiwan phone number scam detection."""

import re
import logging
from typing import Optional

from app.models.schemas import AnalysisResult
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

# ============================================================
# Taiwan phone number patterns
# ============================================================

# Mobile: 09xx-xxx-xxx
MOBILE_PATTERN = re.compile(r"^09\d{8}$")

# Landline by area: 02 (Taipei), 03 (Taoyuan/Hsinchu), 04 (Taichung), etc.
LANDLINE_PATTERN = re.compile(r"^0[2-9]\d{7,8}$")

# International prefix
INTL_PATTERN = re.compile(r"^\+?\d{10,15}$")

# Known suspicious prefixes (international scam hotspots)
SUSPICIOUS_INTL_PREFIXES = {
    "+86": "中國",
    "+855": "柬埔寨",
    "+856": "寮國",
    "+95": "緬甸",
    "+234": "奈及利亞",
    "+233": "迦納",
    "+63": "菲律賓",
    "+84": "越南",
}

# Known official / government numbers
OFFICIAL_NUMBERS = {
    "165": {"name": "165 反詐騙專線", "safe": True},
    "110": {"name": "110 報案專線", "safe": True},
    "113": {"name": "113 保護專線", "safe": True},
    "119": {"name": "119 消防救護", "safe": True},
    "1922": {"name": "1922 防疫專線", "safe": True},
    "1925": {"name": "1925 安心專線", "safe": True},
    "1955": {"name": "1955 勞工權益專線", "safe": True},
    "1980": {"name": "1980 張老師專線", "safe": True},
    "1999": {"name": "1999 市民服務專線", "safe": True},
}

# Known telecom short codes (legitimate)
TELECOM_SHORT_CODES = {
    "123": "中華電信客服",
    "125": "台灣大哥大客服",
    "180": "遠傳客服",
    "111": "政府簡訊平台",
}

# Common scam patterns in phone numbers
# - Numbers with many repeated digits
# - Numbers that look like they're spoofed to resemble official ones


def normalize_phone(raw: str) -> str:
    """Normalize phone number: remove spaces, dashes, parentheses."""
    cleaned = re.sub(r"[\s\-\(\)\.\+]", "", raw)
    # Handle +886 country code
    if cleaned.startswith("886") and len(cleaned) > 9:
        cleaned = "0" + cleaned[3:]
    return cleaned


def classify_phone(number: str) -> dict:
    """Classify a phone number and return metadata."""
    raw = number
    number = normalize_phone(number)

    # Check official numbers first
    if number in OFFICIAL_NUMBERS:
        info = OFFICIAL_NUMBERS[number]
        return {"type": "official", "label": info["name"], "safe": True, "number": number}

    if number in TELECOM_SHORT_CODES:
        return {"type": "telecom", "label": TELECOM_SHORT_CODES[number], "safe": True, "number": number}

    # Check international suspicious prefixes
    for prefix, country in SUSPICIOUS_INTL_PREFIXES.items():
        clean_prefix = prefix.replace("+", "")
        if number.startswith(clean_prefix) or raw.startswith(prefix):
            return {"type": "international_suspicious", "label": f"國際電話（{country}）", "country": country, "safe": False, "number": raw}

    # Taiwan mobile
    if MOBILE_PATTERN.match(number):
        return {"type": "mobile", "label": "台灣手機號碼", "safe": None, "number": number}

    # Taiwan landline
    if LANDLINE_PATTERN.match(number):
        area = _get_area_name(number)
        return {"type": "landline", "label": f"台灣市話（{area}）", "safe": None, "number": number}

    # Other international
    if len(number) >= 10 and number.isdigit():
        return {"type": "international", "label": "國際電話號碼", "safe": None, "number": number}

    return {"type": "unknown", "label": "無法辨識的號碼格式", "safe": None, "number": raw}


def _get_area_name(number: str) -> str:
    """Get area name from Taiwan landline prefix."""
    area_codes = {
        "02": "台北/新北",
        "03": "桃園/新竹/宜蘭/花蓮",
        "04": "台中/彰化",
        "05": "嘉義/雲林",
        "06": "台南",
        "07": "高雄",
        "08": "屏東/台東",
        "037": "苗栗",
        "049": "南投",
        "089": "台東",
    }
    for prefix, name in sorted(area_codes.items(), key=lambda x: -len(x[0])):
        if number.startswith(prefix):
            return name
    return "未知區域"


# ============================================================
# Risk scoring
# ============================================================

def score_phone(phone_info: dict, blacklist_hit: bool = False, report_count: int = 0) -> int:
    """Calculate risk score for a phone number."""
    score = 20  # baseline

    phone_type = phone_info.get("type")

    # Official numbers are safe
    if phone_type == "official" or phone_type == "telecom":
        return 0

    # International from suspicious countries
    if phone_type == "international_suspicious":
        score += 35
        country = phone_info.get("country", "")
        if country in ("柬埔寨", "緬甸", "寮國"):
            score += 15  # extra risk for known scam hubs

    # International (unknown country)
    if phone_type == "international":
        score += 15

    # Blacklist hit
    if blacklist_hit:
        score += 30

    # Community reports
    if report_count > 0:
        score += min(report_count * 8, 30)

    # Number pattern analysis
    number = phone_info.get("number", "")
    normalized = normalize_phone(number)

    # Repeated digits (e.g., 0900000000)
    if len(set(normalized[-6:])) <= 2:
        score += 10

    return max(0, min(100, score))


# ============================================================
# Main entry point
# ============================================================

def _score_to_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _build_phone_explanation(score: int, phone_info: dict, report_count: int) -> str:
    """Build explanation in friendly Traditional Chinese."""
    phone_type = phone_info.get("type")
    label = phone_info.get("label", "")
    number = phone_info.get("number", "")

    if phone_type == "official" or phone_type == "telecom":
        return f"這是「{label}」，是官方/合法號碼，可以安心接聽或撥打。"

    parts = []
    if phone_type == "international_suspicious":
        country = phone_info.get("country", "")
        parts.append(f"這是來自{country}的國際電話。{country}是已知的詐騙高風險地區，台灣很多詐騙集團都設在那邊。")
        parts.append("如果你沒有認識的人在那個國家，幾乎可以確定是詐騙電話。")
    elif phone_type == "international":
        parts.append("這是一組國際電話號碼。如果你沒有預期會收到國際來電，要特別注意。")
    elif phone_type == "mobile":
        if score < 35:
            parts.append(f"這是一般的台灣手機號碼（{number}），目前沒有發現明顯的可疑紀錄。")
        else:
            parts.append(f"這組台灣手機號碼（{number}）有一些需要注意的地方。")
    elif phone_type == "landline":
        parts.append(f"這是{label}（{number}）。")

    if report_count > 0:
        parts.append(f"這個號碼已經被 {report_count} 位使用者回報過是可疑號碼。")

    if not parts:
        parts.append(f"查詢號碼：{number}")

    return "\n".join(parts)


def _build_phone_flags(phone_info: dict, report_count: int) -> list[str]:
    """Build flag list for phone analysis."""
    flags = []
    phone_type = phone_info.get("type")

    if phone_type == "international_suspicious":
        country = phone_info.get("country", "")
        flags.append(f"來自詐騙高風險地區（{country}）")
    if phone_type == "international":
        flags.append("國際電話號碼")
    if report_count > 0:
        flags.append(f"已被 {report_count} 人回報為可疑號碼")
    if phone_type == "official":
        flags.append(f"官方號碼：{phone_info.get('label', '')}")

    return flags


def _build_phone_action(score: int, phone_info: dict) -> str:
    """Build action suggestion."""
    if phone_info.get("type") in ("official", "telecom"):
        return "這是官方號碼，可以安心使用。"

    if score < 30:
        return "目前沒有發現可疑紀錄。如果對方開始談到投資、匯款或索取個資，就要小心了。"
    if score < 60:
        return "建議先不要接聽或回撥。如果已經接了，不要提供任何個人資訊或匯款。可以用 Whoscall App 進一步查詢。"
    if score < 80:
        return "這個號碼很可疑，建議直接封鎖。如果對方聲稱是銀行或政府機關，請自行撥打該機構的官方電話確認，不要回撥這個號碼。"
    return "非常可疑！請直接封鎖這個號碼。如果已經有金錢損失，請立即撥打 165 反詐騙專線報案。"


async def analyze_phone(phone_raw: str) -> AnalysisResult:
    """Analyze a phone number for scam risk."""
    phone_raw = phone_raw.strip()

    # Check cache
    cached = await cache_get(f"phone:{phone_raw}")
    if cached:
        return AnalysisResult(**cached)

    # Classify the number
    phone_info = classify_phone(phone_raw)

    # TODO: query blacklist database for this number
    blacklist_hit = False
    report_count = 0

    # Score
    score = score_phone(phone_info, blacklist_hit, report_count)
    level = _score_to_level(score)
    flags = _build_phone_flags(phone_info, report_count)
    explanation = _build_phone_explanation(score, phone_info, report_count)
    action = _build_phone_action(score, phone_info)

    result = AnalysisResult(
        query_type="phone",
        score=score,
        level=level,
        flags=flags,
        explanation=explanation,
        action=action,
        details=phone_info,
        engine="rule",
    )

    # Cache
    await cache_set(f"phone:{phone_raw}", result.model_dump(), ttl=3600)

    return result
