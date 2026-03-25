"""Tests for ScamRadar content analyzer."""

import pytest
from app.services.content_analyzer import run_rule_engine, score_to_level


class TestRuleEngine:
    """Test the regex-based rule engine."""

    def test_investment_scam(self):
        text = "穩賺不賠的投資機會，月入十萬不是夢！立即加LINE：money888"
        result = run_rule_engine(text)
        assert result.score >= 40
        types = {f.scam_type for f in result.flags}
        assert "investment" in types
        assert "redirect" in types

    def test_phishing_vote(self):
        text = "幫我們家寵物投票好嗎？先登入LINE，輸入認證碼就可以投票了"
        result = run_rule_engine(text)
        assert result.score >= 40
        types = {f.scam_type for f in result.flags}
        assert "phishing_vote" in types
        assert "credential_theft" in types

    def test_lottery_scam(self):
        text = "恭喜您中獎了！限時24小時，請立即匯款手續費到帳戶 012-345678"
        result = run_rule_engine(text)
        assert result.score >= 40
        types = {f.scam_type for f in result.flags}
        assert "lottery_scam" in types
        assert "urgency" in types
        assert "financial" in types

    def test_job_scam(self):
        text = "在家兼職日薪3000，加LINE了解詳情，在线咨询"
        result = run_rule_engine(text)
        assert result.score >= 30
        types = {f.scam_type for f in result.flags}
        assert "job_scam" in types
        assert "simplified_chinese" in types

    def test_normal_message(self):
        text = "明天下午三點在公司開會，記得帶筆電"
        result = run_rule_engine(text)
        assert result.score < 20
        assert len(result.flags) == 0

    def test_normal_greeting(self):
        text = "嗨，好久不見！最近過得怎麼樣？"
        result = run_rule_engine(text)
        assert result.score == 0

    def test_credential_theft_highest_severity(self):
        text = "請提供你的認證碼來完成安全驗證"
        result = run_rule_engine(text)
        assert result.score >= 25
        crit_flags = [f for f in result.flags if f.severity == "critical"]
        assert len(crit_flags) > 0

    def test_multiple_patterns_accumulate(self):
        text = "限時優惠！穩賺不賠的投資，立即匯款加LINE：invest888，恭喜中獎"
        result = run_rule_engine(text)
        assert result.score >= 60
        assert len(result.flags) >= 4


class TestScoreToLevel:

    def test_low(self):
        assert score_to_level(0) == "low"
        assert score_to_level(34) == "low"

    def test_medium(self):
        assert score_to_level(35) == "medium"
        assert score_to_level(59) == "medium"

    def test_high(self):
        assert score_to_level(60) == "high"
        assert score_to_level(79) == "high"

    def test_critical(self):
        assert score_to_level(80) == "critical"
        assert score_to_level(100) == "critical"
