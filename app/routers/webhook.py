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
from app.services.reply_builder import (
    build_reply, build_welcome_message, build_processing_message,
    build_feedback_thanks, build_report_thanks, build_error_message,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify LINE webhook signature."""
    settings = get_settings()
    secret = settings.line_channel_secret.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(signature, expected)


async def _reply(reply_token: str, messages: list[dict]) -> None:
    """Send reply messages via LINE Messaging API."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.line_channel_access_token}",
                },
                json={"replyToken": reply_token, "messages": messages[:5]},  # LINE max 5
            )
            if resp.status_code != 200:
                logger.error(f"LINE reply failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"LINE reply error: {e}")


async def _get_message_content(message_id: str) -> bytes:
    """Download image/file content from LINE."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api-data.line.me/v2/bot/message/{message_id}/content",
            headers={"Authorization": f"Bearer {settings.line_channel_access_token}"},
        )
        resp.raise_for_status()
        return resp.content


# ============================================================
# Webhook endpoint
# ============================================================

@router.post("/webhook")
async def handle_webhook(request: Request):
    """Main LINE webhook endpoint."""
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # Verify signature (skip if no secret configured — for local testing)
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
            if reply_token:
                await _reply(reply_token, [build_error_message()])

    return {"status": "ok"}


async def _handle_event(event: dict):
    """Dispatch a single LINE event."""
    event_type = event.get("type")
    reply_token = event.get("replyToken")

    if event_type == "follow":
        # User added bot as friend
        await _reply(reply_token, [build_welcome_message()])
        return

    if event_type == "message":
        await _handle_message(event, reply_token)
        return

    if event_type == "postback":
        await _handle_postback(event, reply_token)
        return


async def _handle_message(event: dict, reply_token: str):
    """Handle incoming message events."""
    message = event.get("message", {})
    msg_type = message.get("type")
    user_id = event.get("source", {}).get("userId")

    if msg_type == "text":
        text = message.get("text", "").strip()
        if not text:
            return

        # Analyze
        result = await route_message(text, user_id=user_id)
        flex = build_reply(result)
        await _reply(reply_token, [flex])

    elif msg_type == "image":
        # TODO: OCR integration
        # For now, inform user that image analysis is coming soon
        await _reply(reply_token, [{
            "type": "text",
            "text": "收到截圖了！截圖辨識功能正在開發中，目前可以先幫你分析文字訊息和網址。\n\n請把截圖裡的文字複製貼上給我，我來幫你分析～",
        }])

    else:
        await _reply(reply_token, [{
            "type": "text",
            "text": "目前支援文字訊息和網址查詢喔！\n\n你可以：\n• 直接傳可疑訊息給我\n• 輸入 @帳號名稱 查帳號\n• 貼上網址幫你檢查",
        }])


async def _handle_postback(event: dict, reply_token: str):
    """Handle postback events (button clicks)."""
    data = event.get("postback", {}).get("data", "")
    parts = data.split(":")

    if len(parts) < 3:
        return

    action, sub_action, query_id = parts[0], parts[1], parts[2]

    if action == "feedback":
        # TODO: save feedback to database
        await _reply(reply_token, [build_feedback_thanks()])

    elif action == "report":
        # TODO: save report to database, update blacklist
        await _reply(reply_token, [build_report_thanks()])
