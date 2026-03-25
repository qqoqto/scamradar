"""Message router — classifies and dispatches LINE messages to analyzers."""

import re
import time
import logging
from typing import Optional

from app.models.schemas import AnalysisResult
from app.services.content_analyzer import analyze_content
from app.services.account_analyzer import analyze_account
from app.services.url_analyzer import analyze_url
from app.services.phone_analyzer import analyze_phone
from app.services.reply_builder import build_reply, build_processing_message

logger = logging.getLogger(__name__)

# Patterns
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|"
    r"(?:bit\.ly|reurl\.cc|tinyurl\.com|goo\.gl|t\.co)/[^\s<>\"']+",
    re.IGNORECASE,
)
USERNAME_PATTERN = re.compile(r"^[@＠]\s*(\S+)$")

# Phone: Taiwan mobile (09xx), landline (0x-xxxx), international (+xxx), or short codes
PHONE_PATTERN = re.compile(
    r"^[\+＋]?\d[\d\s\-\(\)\.]{6,17}$"
)
# Stricter check after cleanup
PHONE_CLEAN_PATTERN = re.compile(
    r"^(?:09\d{8}|0[2-9]\d{7,8}|\+?\d{10,15}|165|110|113|119|1922|1925|1955|1980|1999)$"
)


def classify_message(text: str) -> tuple[str, str]:
    """Classify message type and extract the query target.

    Returns (query_type, cleaned_input):
        - ("account", "username")
        - ("phone", "0912345678")
        - ("url", "https://...")
        - ("content", "original text")
    """
    text = text.strip()

    # 1. Username query: starts with @ or ＠
    m = USERNAME_PATTERN.match(text)
    if m:
        return "account", m.group(1).strip()

    # 2. Phone number: digits with optional dashes/spaces/plus
    if PHONE_PATTERN.match(text):
        cleaned = re.sub(r"[\s\-\(\)\.]", "", text)
        cleaned = cleaned.replace("＋", "+")
        if PHONE_CLEAN_PATTERN.match(cleaned):
            return "phone", cleaned

    # 3. URL: if message is predominantly a URL (not buried in long text)
    urls = URL_PATTERN.findall(text)
    if urls:
        url_len = len(urls[0])
        non_url_len = len(text) - url_len
        if non_url_len < 60:
            return "url", urls[0]

    # 4. Everything else → content analysis
    return "content", text


async def route_message(text: str, user_id: Optional[str] = None) -> AnalysisResult:
    """Route a text message to the appropriate analyzer and return the result."""
    start = time.time()
    query_type, cleaned = classify_message(text)

    logger.info(f"Routing message: type={query_type}, user={user_id}, input_len={len(cleaned)}")

    if query_type == "account":
        result = await analyze_account(cleaned)
    elif query_type == "phone":
        result = await analyze_phone(cleaned)
    elif query_type == "url":
        result = await analyze_url(cleaned)
    else:
        result = await analyze_content(cleaned)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(f"Analysis complete: type={query_type}, score={result.score}, engine={result.engine}, time={elapsed_ms}ms")

    return result
