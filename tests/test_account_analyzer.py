"""Tests for ScamRadar account analyzer."""

import pytest
from app.services.account_analyzer import score_account, _has_excessive_numbers, _has_random_pattern
from app.models.schemas import AccountFeatures


def _make_features(**overrides) -> AccountFeatures:
    defaults = dict(
        username="normal_user",
        platform="instagram",
        account_age_days=365,
        followers=500,
        following=300,
        post_count=50,
        has_profile_pic=True,
        has_bio=True,
        is_verified=False,
        engagement_rate=3.5,
        cross_platform_count=2,
        in_blacklist=False,
        report_count=0,
    )
    defaults.update(overrides)
    return AccountFeatures(**defaults)


class TestAccountScoring:

    def test_normal_account_low_risk(self):
        f = _make_features()
        score = score_account(f)
        assert score < 40

    def test_new_account_higher_risk(self):
        f = _make_features(account_age_days=3)
        score = score_account(f)
        assert score >= 50

    def test_no_profile_pic_adds_risk(self):
        normal = score_account(_make_features())
        no_pic = score_account(_make_features(has_profile_pic=False))
        assert no_pic > normal

    def test_verified_reduces_risk(self):
        normal = score_account(_make_features())
        verified = score_account(_make_features(is_verified=True))
        assert verified < normal

    def test_suspicious_ratio(self):
        f = _make_features(followers=5, following=4000)
        score = score_account(f)
        assert score >= 50

    def test_no_posts_but_many_followers(self):
        f = _make_features(post_count=1, followers=2000, following=100)
        score = score_account(f)
        assert score >= 40

    def test_blacklisted_account(self):
        f = _make_features(in_blacklist=True)
        score = score_account(f)
        assert score >= 55

    def test_many_reports(self):
        f = _make_features(report_count=5)
        score = score_account(f)
        normal = score_account(_make_features())
        assert score > normal

    def test_bot_username_numbers(self):
        f = _make_features(username="user238947234")
        score = score_account(f)
        normal = score_account(_make_features())
        assert score > normal

    def test_score_clamps_to_100(self):
        f = _make_features(
            account_age_days=1, followers=0, following=5000,
            has_profile_pic=False, has_bio=False, post_count=0,
            in_blacklist=True, report_count=10,
            username="xbot38274923",
        )
        score = score_account(f)
        assert score == 100

    def test_score_clamps_to_0(self):
        f = _make_features(
            is_verified=True, cross_platform_count=5,
            account_age_days=3000,
        )
        score = score_account(f)
        assert score >= 0


class TestUsernamePatterns:

    def test_excessive_numbers_true(self):
        assert _has_excessive_numbers("bot23894723") is True
        assert _has_excessive_numbers("user_20240101") is True

    def test_excessive_numbers_false(self):
        assert _has_excessive_numbers("john_doe") is False
        assert _has_excessive_numbers("cafe123") is False

    def test_random_pattern_true(self):
        assert _has_random_pattern("xkjfqwzts") is True
        assert _has_random_pattern("bcdfghjkl") is True

    def test_random_pattern_false(self):
        assert _has_random_pattern("hello_world") is False
        assert _has_random_pattern("taiwan_food") is False
        assert _has_random_pattern("ab") is False  # too short
