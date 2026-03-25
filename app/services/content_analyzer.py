"""Content analyzer — rule engine + Claude API dual-layer scam detection."""

import re
import json
import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.models.schemas import AnalysisResult, ContentFlag, RuleEngineResult

logger = logging.getLogger(__name__)

# ============================================================
# Rule Engine — fast keyword/regex pattern matching
# ============================================================

SCAM_PATTERNS = [
    # 投資詐騙
    {"pattern": r"(穩賺不賠|保證獲利|日入\d+|月入\d+|零風險投資|翻倍|高報酬)",
     "type": "investment", "score": 20, "label": "含投資詐騙話術", "severity": "high"},

    # 催促策略
    {"pattern": r"(限時\d*|緊急|立即|馬上|最後機會|倒數|即將截止|錯過不再)",
     "type": "urgency", "score": 10, "label": "使用催促性話術", "severity": "medium"},

    # 金融交易要求
    {"pattern": r"(匯款|轉帳|銀行卡[號]?|帳[戶號]|ATM|虛擬帳號|代收)",
     "type": "financial", "score": 15, "label": "要求金融交易", "severity": "high"},

    # 誘導轉移到私訊
    {"pattern": r"(加\s?[Ll][Ii][Nn][Ee]|加\s?賴|私訊我|加好友|加入群組|私聊)",
     "type": "redirect", "score": 12, "label": "誘導轉移到私人通訊", "severity": "high"},

    # 帳號憑證竊取
    {"pattern": r"(認證碼|驗證碼|登入密碼|OTP|一次性密碼|安全碼)",
     "type": "credential_theft", "score": 25, "label": "索取帳號憑證資訊", "severity": "critical"},

    # 釣魚投票
    {"pattern": r"(幫忙投票|幫我投票|寵物投票|繪畫[比賽]?投票|作品投票|拉票)",
     "type": "phishing_vote", "score": 20, "label": "疑似投票釣魚手法", "severity": "high"},

    # 可疑短網址
    {"pattern": r"(bit\.ly|reurl\.cc|tinyurl\.com|goo\.gl|t\.co|is\.gd|ppt\.cc)/",
     "type": "suspicious_url", "score": 10, "label": "含短網址（無法直接確認目的地）", "severity": "medium"},

    # 簡體中文混用（疑境外來源）
    {"pattern": r"(在线|咨询|视频|关注|优惠券|红包|直郵|扫码|微信|支付宝)",
     "type": "simplified_chinese", "score": 8, "label": "混用簡體中文用語（疑境外來源）", "severity": "medium"},

    # 假冒官方通知
    {"pattern": r"(客服通知|系統升級|帳號異常|安全驗證|帳號凍結|重新認證|帳戶風險)",
     "type": "impersonation", "score": 12, "label": "假冒官方通知話術", "severity": "high"},

    # 感情詐騙開場
    {"pattern": r"(想認識你|交個朋友|好想你|你好可愛|緣分|天注定|命中注定|一見鍾情)",
     "type": "romance", "score": 8, "label": "疑似感情詐騙開場", "severity": "medium"},

    # 兼職/打工詐騙
    {"pattern": r"(在家[賺兼]|兼職|日薪\d+|時薪\d+|刷單|代購|網路賺錢|躺著賺|被動收入)",
     "type": "job_scam", "score": 15, "label": "含可疑兼職/打工廣告", "severity": "high"},

    # 免費好康（常見假活動）
    {"pattern": r"(免費[領送]|0元|免費貼圖|免費體驗|好康分享|分享.*領取)",
     "type": "fake_freebie", "score": 10, "label": "宣稱免費好康（常見假活動）", "severity": "medium"},

    # 假冒中獎
    {"pattern": r"(恭喜.*中獎|得獎|抽中|幸運兒|獎金|彩金|獎品.*領取)",
     "type": "lottery_scam", "score": 18, "label": "假冒中獎通知", "severity": "high"},
]


def run_rule_engine(text: str) -> RuleEngineResult:
    """Scan text with regex patterns and return accumulated score + flags."""
    flags = []
    total_score = 0

    for rule in SCAM_PATTERNS:
        matches = re.findall(rule["pattern"], text, re.IGNORECASE)
        if matches:
            match_count = len(matches)
            flag = ContentFlag(
                label=f"{rule['label']}（出現 {match_count} 次）",
                score=rule["score"],
                scam_type=rule["type"],
                severity=rule["severity"],
            )
            flags.append(flag)
            total_score += rule["score"]

    total_score = min(100, total_score)
    return RuleEngineResult(score=total_score, flags=flags)


# ============================================================
# Claude API — semantic scam analysis
# ============================================================

CLAUDE_SYSTEM_PROMPT = """你是一個台灣的防詐騙分析專家。你的工作是分析使用者提供的訊息內容，判斷是否包含詐騙特徵。

請以 JSON 格式回覆（不要加 markdown 標記），包含以下欄位：
- risk_score: 0-100 的風險分數
- scam_type: 詐騙類型 (investment/lottery/phishing/romance/job/impersonation/none)
- tactics: 使用的話術策略列表（每項是字串）
- explanation: 給一般民眾看的白話分析（繁體中文，語氣像懂科技的鄰居阿姨，親切但有權威感，不要用「您」，用「你」）
- action_suggestion: 具體的行動建議（繁體中文，要告訴使用者下一步該做什麼）

判斷標準：
- 0-30: 正常訊息，沒有明顯詐騙特徵
- 30-60: 有些可疑，但不確定
- 60-80: 很多詐騙特徵，建議不要互動
- 80-100: 幾乎確定是詐騙

請特別注意台灣常見的詐騙手法：
- LINE 投票釣魚（幫寵物投票、幫小孩作品投票）
- 投資詐騙（穩賺不賠、保證獲利）
- 假冒官方帳號（LINE 客服、銀行通知）
- 感情詐騙（交友軟體認識後要求加 LINE）
- 假中獎通知
- 假兼職/打工（日入數千、在家賺錢）"""


async def call_claude_api(text: str) -> Optional[dict]:
    """Call Claude API for semantic scam analysis."""
    settings = get_settings()
    if not settings.claude_api_key:
        logger.warning("Claude API key not configured, skipping AI analysis")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.claude_model,
                    "max_tokens": 1000,
                    "system": CLAUDE_SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": f"請分析以下訊息：\n\n{text[:2000]}"}
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            raw = data["content"][0]["text"]
            # Strip possible markdown fences
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


# ============================================================
# Combined analyzer
# ============================================================

def score_to_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


async def analyze_content(text: str) -> AnalysisResult:
    """Analyze text content for scam patterns using dual-layer engine."""
    if not text or len(text.strip()) < 3:
        return AnalysisResult(
            query_type="content", score=0, level="low",
            explanation="訊息太短了，沒辦法分析。可以提供更完整的內容嗎？",
            action="試試看把完整的訊息貼過來。",
            engine="rule",
        )

    # Layer 1: Rule engine (fast, free)
    rule_result = run_rule_engine(text)
    rule_flags = [f.label for f in rule_result.flags]

    # If rule engine already high confidence, skip AI to save cost
    if rule_result.score >= 75:
        return AnalysisResult(
            query_type="content",
            score=rule_result.score,
            level=score_to_level(rule_result.score),
            flags=rule_flags,
            explanation=_build_rule_explanation(rule_result),
            action=_build_action(rule_result.score),
            scam_type=_get_primary_scam_type(rule_result),
            engine="rule",
        )

    # Layer 2: Claude API (semantic, paid)
    ai_result = await call_claude_api(text)

    if ai_result:
        # Merge scores: take the higher of rule vs AI
        ai_score = ai_result.get("risk_score", 0)
        final_score = max(rule_result.score, ai_score)
        ai_flags = ai_result.get("tactics", [])
        all_flags = list(set(rule_flags + ai_flags))

        return AnalysisResult(
            query_type="content",
            score=final_score,
            level=score_to_level(final_score),
            flags=all_flags,
            explanation=ai_result.get("explanation", ""),
            action=ai_result.get("action_suggestion", _build_action(final_score)),
            scam_type=ai_result.get("scam_type", "none"),
            engine="hybrid",
        )

    # AI unavailable, fall back to rule engine only
    return AnalysisResult(
        query_type="content",
        score=rule_result.score,
        level=score_to_level(rule_result.score),
        flags=rule_flags,
        explanation=_build_rule_explanation(rule_result),
        action=_build_action(rule_result.score),
        scam_type=_get_primary_scam_type(rule_result),
        engine="rule",
    )


def _build_rule_explanation(result: RuleEngineResult) -> str:
    if result.score < 20:
        return "這則訊息看起來沒什麼明顯的問題，不過還是多留意比較好。"
    if result.score < 50:
        return "這則訊息有一些可疑的地方，建議你多想一下再決定要不要回應。"
    if result.score < 75:
        return "這則訊息包含不少詐騙常見的特徵，建議你不要理會，也不要點擊任何連結。"
    return "這則訊息有非常多詐騙的特徵，幾乎可以確定是詐騙。請不要回覆、不要匯款、不要提供任何個人資訊。"


def _build_action(score: int) -> str:
    if score < 20:
        return "沒什麼大問題，正常互動就好。"
    if score < 50:
        return "建議先不要回覆，觀察一下對方後續的行為。如果要求匯款或提供個資，就是詐騙。"
    if score < 75:
        return "建議封鎖對方並檢舉。如果已經有金錢損失，請撥打 165 反詐騙專線報案。"
    return "請立即封鎖檢舉！不要匯款、不要點連結、不要提供個資。如有損失請立即撥打 165 反詐騙專線。"


def _get_primary_scam_type(result: RuleEngineResult) -> str:
    if not result.flags:
        return "none"
    # Return the type of the highest-scoring flag
    top = max(result.flags, key=lambda f: f.score)
    return top.scam_type
