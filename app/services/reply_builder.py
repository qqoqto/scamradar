"""Reply builder — constructs LINE Flex Messages from analysis results."""

from app.models.schemas import AnalysisResult

LEVEL_CONFIG = {
    "low":      {"color": "#639922", "bg": "#EAF3DE", "icon": "✅", "label": "看起來正常"},
    "medium":   {"color": "#BA7517", "bg": "#FAEEDA", "icon": "⚠️", "label": "有點可疑，留意一下"},
    "high":     {"color": "#E24B4A", "bg": "#FCEBEB", "icon": "🚨", "label": "很多可疑特徵"},
    "critical": {"color": "#791F1F", "bg": "#FCEBEB", "icon": "🛑", "label": "非常危險"},
}

TYPE_LABELS = {
    "account": "帳號分析",
    "content": "內容分析",
    "url": "網址檢查",
    "image": "截圖分析",
}


def build_reply(result: AnalysisResult) -> dict:
    """Build a LINE Flex Message JSON from analysis result."""
    cfg = LEVEL_CONFIG.get(result.level, LEVEL_CONFIG["medium"])
    type_label = TYPE_LABELS.get(result.query_type, "分析")

    # Flags as bullet list (max 5)
    flag_items = []
    for flag in result.flags[:5]:
        flag_items.append({
            "type": "text",
            "text": f"• {flag}",
            "size": "xs",
            "color": "#666666",
            "wrap": True,
            "margin": "sm",
        })

    body_contents = [
        # Explanation
        {
            "type": "text",
            "text": result.explanation or "分析完成。",
            "size": "sm",
            "color": "#333333",
            "wrap": True,
        },
    ]

    if flag_items:
        body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.extend(flag_items)

    if result.action:
        body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.append({
            "type": "text",
            "text": f"💡 {result.action}",
            "size": "sm",
            "color": "#333333",
            "wrap": True,
            "weight": "bold",
        })

    flex_message = {
        "type": "flex",
        "altText": f"{cfg['icon']} {cfg['label']}（{type_label}）",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": cfg["bg"],
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{cfg['icon']} {cfg['label']}",
                        "size": "lg",
                        "weight": "bold",
                        "color": cfg["color"],
                    },
                    {
                        "type": "text",
                        "text": f"{type_label} ─ 風險分數 {result.score}/100",
                        "size": "xs",
                        "color": "#888888",
                        "margin": "sm",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "spacing": "sm",
                "contents": body_contents,
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "👍 有幫助",
                            "data": f"feedback:helpful:{result.id or 0}",
                        },
                        "style": "secondary",
                        "height": "sm",
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🚩 回報詐騙",
                            "data": f"report:scam:{result.id or 0}",
                        },
                        "style": "primary",
                        "height": "sm",
                        "color": cfg["color"],
                    },
                ],
            },
        },
    }
    return flex_message


def build_welcome_message() -> dict:
    """Build the welcome Flex Message shown when user adds the bot."""
    return {
        "type": "flex",
        "altText": "歡迎使用 ScamRadar 獵詐雷達！",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "backgroundColor": "#EEEDFE",
                "contents": [
                    {
                        "type": "text",
                        "text": "🛡️ ScamRadar 獵詐雷達",
                        "size": "xl",
                        "weight": "bold",
                        "color": "#3C3489",
                    },
                    {
                        "type": "text",
                        "text": "你的防詐好幫手！把可疑的東西丟給我分析～",
                        "size": "sm",
                        "color": "#534AB7",
                        "margin": "md",
                        "wrap": True,
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "spacing": "lg",
                "contents": [
                    _feature_row("💬", "轉傳可疑訊息", "直接把可疑的文字訊息傳給我"),
                    _feature_row("👤", "查帳號", "輸入 @帳號名稱 幫你分析可信度"),
                    _feature_row("🔗", "查網址", "貼上連結幫你確認安全性"),
                    _feature_row("📸", "傳截圖", "傳可疑訊息的截圖，我會辨識分析"),
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "text",
                        "text": "遇到詐騙請撥 165 反詐騙專線",
                        "size": "xs",
                        "color": "#999999",
                        "align": "center",
                    },
                ],
            },
        },
    }


def build_processing_message() -> dict:
    """Simple text message shown while processing."""
    return {
        "type": "text",
        "text": "收到！正在幫你分析中，請稍等幾秒⋯⋯",
    }


def build_feedback_thanks() -> dict:
    return {"type": "text", "text": "謝謝你的回饋！你的意見會幫助我們變得更準確 🙏"}


def build_report_thanks(report_count: int = 0) -> dict:
    text = "已經收到你的回報，這筆資料會加入我們的資料庫，幫助保護更多人。"
    if report_count > 1:
        text += f"\n目前共有 {report_count} 位使用者回報過類似的內容。"
    text += "\n感謝你的正義感！💪"
    return {"type": "text", "text": text}


def build_error_message() -> dict:
    return {
        "type": "text",
        "text": "抱歉，分析過程中出了點問題 😅 請稍後再試一次，或換個方式描述看看。",
    }


def _feature_row(icon: str, title: str, desc: str) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "md",
        "contents": [
            {"type": "text", "text": icon, "size": "xl", "flex": 0},
            {
                "type": "box",
                "layout": "vertical",
                "flex": 5,
                "contents": [
                    {"type": "text", "text": title, "size": "sm", "weight": "bold"},
                    {"type": "text", "text": desc, "size": "xs", "color": "#888888", "wrap": True},
                ],
            },
        ],
    }
