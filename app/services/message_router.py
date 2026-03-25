"""Message router — classifies and dispatches LINE messages to analyzers."""

import re
import time
import logging
from typing import Optional

from app.models.schemas import AnalysisResult
from app.services.content_analyzer import analyze_content
from app.services.account_analyzer import analyze_account
from app.services.url_analyzer import analyze_url
from app.services.reply_builder import build_reply, build_processing_message

logger = logging.getLogger(__name__)

# Patterns
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|"
    r"(?:bit\.ly|reurl\.cc|tinyurl\.com|goo\.gl|t\.co)/[^\s<>\"']+",
    re.IGNORECASE,
)
USERNAME_PATTERN = re.compile(r"^[@＠]\s*(\S+)$")


def classify_message(text: str) -> tuple[str, str]:
    """Classify message type and extract the query target.

    Returns (query_type, cleaned_input):
        - ("account", "username")
        - ("url", "https://...")
        - ("content", "original text")
    """
    text = text.strip()

    # 1. Username query: starts with @ or ＠
    m = USERNAME_PATTERN.match(text)
    if m:
        return "account", m.group(1).strip()

    # 2. URL: if message is predominantly a URL (not buried in long text)
    urls = URL_PATTERN.findall(text)
    if urls:
        # Only classify as URL if the URL makes up the bulk of the message
        url_len = len(urls[0])
        non_url_len = len(text) - url_len
        if non_url_len < 60:
            return "url", urls[0]

    # 3. Everything else → content analysis
    return "content", text


async def route_message(text: str, user_id: Optional[str] = None) -> AnalysisResult:
    """Route a text message to the appropriate analyzer and return the result."""
    start = time.time()
    query_type, cleaned = classify_message(text)

    logger.info(f"Routing message: type={query_type}, user={user_id}, input_len={len(cleaned)}")

    if query_type == "account":
        result = await analyze_account(cleaned)
    elif query_type == "url":
        result = await analyze_url(cleaned)
    else:
        result = await analyze_content(cleaned)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(f"Analysis complete: type={query_type}, score={result.score}, engine={result.engine}, time={elapsed_ms}ms")

    return result
