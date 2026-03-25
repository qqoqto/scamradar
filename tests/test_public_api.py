"""
Phase 2 — Public API unit tests.
Validates request/response schemas, rate limiting, and helper logic.
Run: pytest tests/test_public_api.py -v
"""

import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from app.routers.public_api import (
    CheckPhoneRequest, CheckUrlRequest, CheckUsernameRequest, CheckContentRequest,
    CheckResponse, StatsResponse, BlacklistEntry,
    _check_rate_limit, _rate_limits, _to_check_response,
    RATE_LIMIT_MAX,
)
from app.models.schemas import AnalysisResult


# ─── Request schema tests ────────────────────────────────────────

class TestRequestSchemas:
    def test_phone_valid(self):
        req = CheckPhoneRequest(phone="+886912345678")
        assert req.phone == "+886912345678"

    def test_phone_too_short(self):
        with pytest.raises(ValidationError):
            CheckPhoneRequest(phone="12")

    def test_url_valid(self):
        req = CheckUrlRequest(url="https://example.com/path?q=1")
        assert req.url.startswith("https://")

    def test_url_too_short(self):
        with pytest.raises(ValidationError):
            CheckUrlRequest(url="h")

    def test_username_valid(self):
        req = CheckUsernameRequest(username="@scammer123")
        assert req.username == "@scammer123"

    def test_content_valid(self):
        req = CheckContentRequest(content="恭喜您中獎了！請點選連結領取獎金")
        assert "中獎" in req.content

    def test_content_empty_rejected(self):
        with pytest.raises(ValidationError):
            CheckContentRequest(content="")


# ─── Response schema tests ───────────────────────────────────────

class TestResponseSchemas:
    def test_check_response(self):
        resp = CheckResponse(
            risk_level="high",
            risk_score=78,
            summary="偵測到投資詐騙特徵",
            action="建議直接封鎖",
            flags=["投資詐騙話術", "要求轉帳"],
            details={"type": "mobile"},
            engine="hybrid",
            cached=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert resp.risk_level == "high"
        assert resp.risk_score == 78
        assert len(resp.flags) == 2
        assert resp.engine == "hybrid"

    def test_stats_response(self):
        resp = StatsResponse(
            total_queries=1500,
            total_users=230,
            total_reports=89,
            total_blacklisted=45,
            queries_today=32,
            queries_this_week=210,
            top_risk_categories=[{"category": "phone", "count": 500}],
            risk_distribution={"low": 800, "high": 200, "critical": 50},
            daily_trend=[{"date": "2026-03-24", "count": 30}],
        )
        assert resp.total_queries == 1500
        assert "low" in resp.risk_distribution

    def test_blacklist_entry_uses_phase1_fields(self):
        entry = BlacklistEntry(
            target_type="phone",
            target_value="+886900111222",
            platform="all",
            risk_score=92,
            report_count=15,
            source="user_report",
            last_reported="2026-03-24T12:00:00",
        )
        assert entry.target_type == "phone"
        assert entry.target_value == "+886900111222"
        assert entry.report_count == 15


# ─── AnalysisResult → CheckResponse conversion ──────────────────

class TestResponseConversion:
    def test_to_check_response(self):
        ar = AnalysisResult(
            query_type="phone",
            score=45,
            level="medium",
            flags=["國際電話號碼"],
            explanation="這是一組國際電話號碼。",
            action="建議先不要接聽或回撥。",
            details={"type": "international"},
            engine="rule",
        )
        resp = _to_check_response(ar)
        assert resp.risk_level == "medium"
        assert resp.risk_score == 45
        assert resp.summary == "這是一組國際電話號碼。"
        assert resp.action == "建議先不要接聽或回撥。"
        assert resp.flags == ["國際電話號碼"]
        assert resp.engine == "rule"
        assert resp.cached is False

    def test_to_check_response_cached(self):
        ar = AnalysisResult(
            query_type="url",
            score=10,
            level="low",
            flags=[],
            explanation="安全",
            action="正常使用",
            engine="rule",
        )
        resp = _to_check_response(ar, cached=True)
        assert resp.cached is True


# ─── Rate limiting tests ────────────────────────────────────────

class TestRateLimiting:
    def setup_method(self):
        _rate_limits.clear()

    def test_allows_within_limit(self):
        for i in range(RATE_LIMIT_MAX):
            assert _check_rate_limit("test_ip") is True

    def test_blocks_over_limit(self):
        for _ in range(RATE_LIMIT_MAX):
            _check_rate_limit("test_ip2")
        assert _check_rate_limit("test_ip2") is False

    def test_different_ips_independent(self):
        for _ in range(RATE_LIMIT_MAX):
            _check_rate_limit("ip_a")
        assert _check_rate_limit("ip_a") is False
        assert _check_rate_limit("ip_b") is True
