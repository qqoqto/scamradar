"""LINE webhook router — handles all incoming LINE events."""

import hashlib
import hmac
import base64
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request, HTTPException

from app.config import get_settings
from app.services.message_router import route_message
from app.services.content_analyzer import run_rule_engine
from app.services.report_service import (
    get_or_create_user, save_query, save_feedback, save_report,
)
from app.services.reply_builder import (
    build_reply, build_reply_group, build_welcome_message,
    build_group_welcome, build_processing_message,
    build_feedback_thanks, build_report_thanks, build_error_message,
)

logger = logging.getLogger(__name__)
router = APIRouter()

GROUP_ALERT_THRESHOLD = 70


def _verify_signature(body: bytes, signature: str) -> bool:
    settings = get_settings()
    secret = settings.line_channel_secret.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(signature, expected)


async def _reply(reply_token: str, messages: list[dict]) -> None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.line_channel_access_token}",
                },
                json={"replyToken": reply_token, "messages": messages[:5]},
            )
            if resp.status_code != 200:
                logger.error(f"LINE reply failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"LINE reply error: {e}")


async def _get_message_content(message_id: str) -> bytes:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api-data.line.me/v2/bot/message/{message_id}/content",
            headers={"Authorization": f"Bearer {settings.line_channel_access_token}"},
        )
        resp.raise_for_status()
        return resp.content


def _is_group_chat(event: dict) -> bool:
    source_type = event.get("source", {}).get("type", "")
    return source_type in ("group", "room")


# ============================================================
# Webhook endpoint
# ============================================================

@router.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    settings = get_settings()
    if settings.line_channel_secret and not _verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = payload.get("events", [])
    for event in events:
        try:
            await _handle_event(event)
        except Exception as e:
            logger.exception(f"Error handling event: {e}")
            reply_token = event.get("replyToken")
            if reply_token and not _is_group_chat(event):
                await _reply(reply_token, [build_error_message()])

    return {"status": "ok"}


async def _handle_event(event: dict):
    event_type = event.get("type")
    reply_token = event.get("replyToken")
    is_group = _is_group_chat(event)

    if event_type == "join":
        await _reply(reply_token, [build_group_welcome()])
        return

    if event_type == "follow":
        await _reply(reply_token, [build_welcome_message()])
        return

    if event_type == "message":
        if is_group:
            await _handle_group_message(event, reply_token)
        else:
            await _handle_message(event, reply_token)
        return

    if event_type == "postback":
        await _handle_postback(event, reply_token)
        return


# ============================================================
# 1-on-1 chat handler
# ============================================================

async def _handle_message(event: dict, reply_token: str):
    message = event.get("message", {})
    msg_type = message.get("type")
    line_user_id = event.get("source", {}).get("userId")

    # Get or create user in DB (non-blocking, OK if DB is down)
    user_id = None
    if line_user_id:
        user_id = await get_or_create_user(line_user_id)

    if msg_type == "text":
        text = message.get("text", "").strip()
        if not text:
            return

        start = time.time()
        result = await route_message(text, user_id=line_user_id)
        elapsed_ms = int((time.time() - start) * 1000)

        # Save query to DB
        query_id = await save_query(
            user_id=user_id,
            query_type=result.query_type,
            input_text=text,
            input_type="text",
            result=result,
            response_time_ms=elapsed_ms,
        )
        result.id = query_id

        flex = build_reply(result)
        await _reply(reply_token, [flex])

    elif msg_type == "image":
        message_id = message.get("id")
        if not message_id:
            return

        try:
            image_data = await _get_message_content(message_id)
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            await _reply(reply_token, [{
                "type": "text",
                "text": "抱歉，圖片下載失敗了。可以重新傳一次嗎？",
            }])
            return

        from app.services.image_analyzer import analyze_image
        start = time.time()
        result = await analyze_image(image_data)
        elapsed_ms = int((time.time() - start) * 1000)

        # Save query to DB
        extracted = result.details.get("extracted_text", "")[: 500] if result.details else ""
        query_id = await save_query(
            user_id=user_id,
            query_type="image",
            input_text=extracted or "(screenshot)",
            input_type="image",
            result=result,
            response_time_ms=elapsed_ms,
        )
        result.id = query_id

        flex = build_reply(result)
        await _reply(reply_token, [flex])

    else:
        await _reply(reply_token, [{
            "type": "text",
            "text": "目前支援文字訊息和網址查詢喔！\n\n你可以：\n• 直接傳可疑訊息給我\n• 輸入 @帳號名稱 查帳號\n• 傳電話號碼查詢\n• 貼上網址幫你檢查\n• 傳截圖幫你辨識",
        }])


# ============================================================
# Group chat handler
# ============================================================

async def _handle_group_message(event: dict, reply_token: str):
    message = event.get("message", {})
    msg_type = message.get("type")

    if msg_type != "text":
        return

    text = message.get("text", "").strip()
    if not text or len(text) < 10:
        return

    rule_result = run_rule_engine(text)
    logger.info(f"Group message scanned: rule_score={rule_result.score}, text_len={len(text)}")

    if rule_result.score < 40:
        return

    result = await route_message(text)

    if result.score >= GROUP_ALERT_THRESHOLD:
        logger.info(f"Group alert triggered: score={result.score}, level={result.level}")
        group_msg = build_reply_group(result)
        await _reply(reply_token, [group_msg])


# ============================================================
# Postback handler (feedback + reports → DB)
# ============================================================

async def _handle_postback(event: dict, reply_token: str):
    data = event.get("postback", {}).get("data", "")
    parts = data.split(":")
    line_user_id = event.get("source", {}).get("userId")

    if len(parts) < 3:
        return

    action, sub_action, query_id_str = parts[0], parts[1], parts[2]

    # Get user id
    user_id = None
    if line_user_id:
        user_id = await get_or_create_user(line_user_id)

    try:
        query_id = int(query_id_str)
    except (ValueError, TypeError):
        query_id = 0

    if action == "feedback":
        is_helpful = sub_action == "helpful"
        if query_id:
            await save_feedback(query_id, user_id, is_helpful)
        await _reply(reply_token, [build_feedback_thanks()])

    elif action == "report":
        report_count = 0
        if query_id:
            report_count = await save_report(query_id, user_id, report_type=sub_action)
        await _reply(reply_token, [build_report_thanks(report_count)])
