"""Tests for ScamRadar message router."""

import pytest
from app.services.message_router import classify_message


class TestMessageClassification:

    def test_username_with_at(self):
        qtype, cleaned = classify_message("@scam_bot_2024")
        assert qtype == "account"
        assert cleaned == "scam_bot_2024"

    def test_username_with_fullwidth_at(self):
        qtype, cleaned = classify_message("＠money_invest")
        assert qtype == "account"
        assert cleaned == "money_invest"

    def test_url_https(self):
        qtype, cleaned = classify_message("https://line-event-prize.top/claim")
        assert qtype == "url"
        assert "line-event-prize.top" in cleaned

    def test_url_shortener(self):
        qtype, cleaned = classify_message("bit.ly/abc123")
        assert qtype == "url"

    def test_content_normal_text(self):
        qtype, cleaned = classify_message("恭喜您中獎了！請立即匯款")
        assert qtype == "content"
        assert "中獎" in cleaned

    def test_content_long_text_with_url(self):
        text = "這個人跟我說投資穩賺不賠 " * 20 + " https://example.com"
        qtype, _ = classify_message(text)
        # Long text with embedded URL → content, not URL
        assert qtype == "content"

    def test_empty_username(self):
        qtype, cleaned = classify_message("@ ")
        # "@" followed by space — not a valid username
        assert qtype == "content"
