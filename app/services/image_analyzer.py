"""Image analyzer — uses Claude Vision to analyze screenshots for scam content."""

import base64
import json
import re
import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.models.schemas import AnalysisResult
from app.services.content_analyzer import run_rule_engine, score_to_level

logger = logging.getLogger(__name__)

VISION_SYSTEM_PROMPT = """你是一個台灣的防詐騙分析專家。使用者傳了一張截圖給你，請仔細看圖片裡的內容，判斷是否包含詐騙特徵。

截圖可能是：
- LINE 聊天對話截圖
- Facebook / Instagram / Threads 的貼文或訊息截圖
- 簡訊截圖
- 一頁式購物網站截圖
- 假中獎通知截圖
- 假投資群組截圖
- 其他任何可疑內容

請以 JSON 格式回覆（不要加 markdown 標記），包含以下欄位：
- extracted_text: 圖片中的主要文字內容（繁體中文）
- risk_score: 0-100 的風險分數
- scam_type: 詐騙類型 (investment/lottery/phishing/romance/job/impersonation/shopping/none)
- tactics: 使用的話術策略列表（每項是字串）
- explanation: 給一般民眾看的白話分析（繁體中文，語氣像懂科技的鄰居阿姨，親切但有權威感，不要用「您」，用「你」）
- action_suggestion: 具體的行動建議（繁體中文，要告訴使用者下一步該做什麼）
- image_type: 截圖類型 (line_chat/facebook/instagram/sms/website/ad/other)

判斷標準：
- 0-30: 正常內容，沒有明顯詐騙特徵
- 30-60: 有些可疑，但不確定
- 60-80: 很多詐騙特徵，建議不要互動
- 80-100: 幾乎確定是詐騙

請特別注意台灣常見的詐騙手法：
- LINE 投票釣魚（幫寵物投票、幫小孩作品投票）
- 投資詐騙（穩賺不賠、保證獲利、報酬率驚人）
- 假冒官方帳號（LINE 客服、銀行通知、系統升級）
- 感情詐騙（交友軟體認識後要求加 LINE）
- 假中獎通知（恭喜得獎、限時領取）
- 假兼職/打工（日入數千、在家賺錢）
- 一頁式詐騙購物網站（超低價、限時限量、貨到付款）
- 假冒名人代言投資廣告

如果圖片看不清楚或不是可疑內容，也請誠實說明。"""


async def analyze_image(image_data: bytes) -> AnalysisResult:
    """Analyze a screenshot image using Claude Vision API."""
    settings = get_settings()

    if not settings.claude_api_key:
        logger.warning("Claude API key not configured, cannot analyze image")
        return AnalysisResult(
            query_type="image",
            score=0,
            level="low",
            explanation="目前截圖分析功能需要 AI 引擎支援，請先用文字方式查詢。",
            action="把截圖裡的文字複製貼上給我，我一樣能幫你分析。",
            engine="rule",
        )

    try:
        b64_image = base64.b64encode(image_data).decode("utf-8")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.claude_model,
                    "max_tokens": 1500,
                    "system": VISION_SYSTEM_PROMPT,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": b64_image,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "請分析這張截圖是否包含詐騙內容。",
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            raw = data["content"][0]["text"]

            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            ai_result = json.loads(raw)

        score = ai_result.get("risk_score", 0)
        extracted_text = ai_result.get("extracted_text", "")

        rule_result = run_rule_engine(extracted_text) if extracted_text else None
        if rule_result and rule_result.score > score:
            score = rule_result.score

        score = max(0, min(100, score))

        flags = ai_result.get("tactics", [])
        if rule_result:
            rule_flags = [f.label for f in rule_result.flags]
            flags = list(set(flags + rule_flags))

        image_type_labels = {
            "line_chat": "LINE 對話截圖",
            "facebook": "Facebook 截圖",
            "instagram": "Instagram 截圖",
            "sms": "簡訊截圖",
            "website": "網站截圖",
            "ad": "廣告截圖",
            "other": "截圖",
        }
        img_type = ai_result.get("image_type", "other")
        type_label = image_type_labels.get(img_type, "截圖")

        explanation = ai_result.get("explanation", "")
        if not explanation:
            explanation = "已分析完這張截圖的內容。"

        return AnalysisResult(
            query_type="image",
            score=score,
            level=score_to_level(score),
            flags=flags,
            explanation=f"【{type_label}分析】\n\n{explanation}",
            action=ai_result.get("action_suggestion", ""),
            scam_type=ai_result.get("scam_type", "none"),
            details={"extracted_text": extracted_text, "image_type": img_type},
            engine="ai",
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude Vision response: {e}")
        return AnalysisResult(
            query_type="image",
            score=0,
            level="low",
            explanation="截圖分析完成，但處理結果時出了點問題。",
            action="可以試著把截圖裡的文字複製貼上給我，我用文字方式再分析一次。",
            engine="ai",
        )
    except Exception as e:
        logger.error(f"Claude Vision API call failed: {e}")
        return AnalysisResult(
            query_type="image",
            score=0,
            level="low",
            explanation="截圖分析暫時無法使用，請稍後再試。",
            action="你也可以把截圖裡的文字複製貼上給我，我一樣能幫你分析。",
            engine="ai",
        )
