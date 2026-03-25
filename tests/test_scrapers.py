"""
Phase 3 — Scraper + account analyzer integration tests.
Run: pytest tests/test_scrapers.py -v
"""

import pytest
from app.scrapers import _detect_platform_hint, _score_features
from app.scrapers.instagram import _parse_count as ig_parse_count, _parse_meta_tags
from app.scrapers.x_twitter import _parse_count as x_parse_count
from app.models.schemas import AccountFeatures


# ─── Platform hint detection ─────────────────────────────────────

class TestPlatformHint:
    def test_ig_hint(self):
        platform, username = _detect_platform_hint("ig:johndoe")
        assert platform == "instagram"
        assert username == "johndoe"

    def test_instagram_hint(self):
        platform, username = _detect_platform_hint("instagram:@johndoe")
        assert platform == "instagram"
        assert username == "johndoe"

    def test_threads_hint(self):
        platform, username = _detect_platform_hint("threads:user123")
        assert platform == "threads"
        assert username == "user123"

    def test_fb_hint(self):
        platform, username = _detect_platform_hint("fb:page.name")
        assert platform == "facebook"
        assert username == "page.name"

    def test_x_hint(self):
        platform, username = _detect_platform_hint("x:elonmusk")
        assert platform == "x"
        assert username == "elonmusk"

    def test_twitter_hint(self):
        platform, username = _detect_platform_hint("twitter:elonmusk")
        assert platform == "x"
        assert username == "elonmusk"

    def test_no_hint(self):
        platform, username = _detect_platform_hint("@regular_user")
        assert platform is None
        assert username == "regular_user"

    def test_no_hint_plain(self):
        platform, username = _detect_platform_hint("some_username")
        assert platform is None
        assert username == "some_username"

    def test_url_not_mistaken_for_hint(self):
        platform, username = _detect_platform_hint("https://example.com")
        assert platform is None


# ─── Feature scoring ─────────────────────────────────────────────

class TestFeatureScoring:
    def test_empty_features_low_score(self):
        f = AccountFeatures(username="test", platform="unknown")
        assert _score_features(f) == 0

    def test_rich_features_high_score(self):
        f = AccountFeatures(
            username="test",
            platform="instagram",
            followers=1500,
            following=300,
            post_count=42,
            bio_text="Hello world",
            account_age_days=365,
        )
        # followers(3) + following(2) + post_count(2) + bio(1) + age(2) + platform(1) = 11
        assert _score_features(f) == 11

    def test_partial_features(self):
        f = AccountFeatures(
            username="test",
            platform="threads",
            followers=100,
        )
        # followers(3) + platform(1) = 4
        assert _score_features(f) == 4


# ─── Count parsing ───────────────────────────────────────────────

class TestCountParsing:
    def test_plain_number(self):
        assert ig_parse_count("1234") == 1234

    def test_comma_number(self):
        assert ig_parse_count("1,234") == 1234

    def test_k_suffix(self):
        assert ig_parse_count("12.5K") == 12500

    def test_m_suffix(self):
        assert ig_parse_count("1.2M") == 1200000

    def test_zero(self):
        assert ig_parse_count("0") == 0

    def test_invalid(self):
        assert ig_parse_count("abc") == 0

    def test_x_parse_count(self):
        assert x_parse_count("45.6K") == 45600


# ─── Instagram meta tag parsing ──────────────────────────────────

class TestInstagramMetaParsing:
    def test_parse_og_description(self):
        html = '''
        <meta property="og:description" content="1,234 Followers, 567 Following, 89 Posts - Hello I am a user" />
        <meta property="og:title" content="Test User (@testuser)" />
        '''
        result = _parse_meta_tags("testuser", html)
        assert result is not None
        assert result.followers == 1234
        assert result.following == 567
        assert result.post_count == 89
        assert result.platform == "instagram"

    def test_parse_no_data(self):
        html = '<html><body>Nothing here</body></html>'
        result = _parse_meta_tags("testuser", html)
        assert result is None

    def test_default_pic_detection(self):
        html = '''
        <meta property="og:description" content="100 Followers, 50 Following, 10 Posts" />
        <img src="https://instagram.com/static/images/anonymousUser.jpg" />
        '''
        result = _parse_meta_tags("testuser", html)
        assert result is not None
        assert result.has_profile_pic is False


# ─── Account analyzer with scraped data ──────────────────────────

class TestAccountScoringWithScrapedData:
    def test_real_account_with_many_followers_lower_risk(self):
        from app.services.account_analyzer import score_account
        f = AccountFeatures(
            username="legitimate_brand",
            platform="instagram",
            followers=5000,
            following=200,
            post_count=150,
            has_profile_pic=True,
            has_bio=True,
            is_verified=False,
            engagement_rate=3.5,
            cross_platform_count=2,
        )
        score = score_account(f)
        # Should be lower risk due to real followers + posts + cross-platform
        assert score < 40

    def test_suspicious_scraped_account(self):
        from app.services.account_analyzer import score_account
        f = AccountFeatures(
            username="xjk38292847",
            platform="instagram",
            followers=2,
            following=800,
            post_count=0,
            has_profile_pic=False,
            has_bio=False,
            is_verified=False,
            engagement_rate=0.0,
            cross_platform_count=0,
        )
        score = score_account(f)
        # Should be high risk: bad ratio, no posts, no pic, no bio, bot username
        assert score >= 70

    def test_verified_account_much_lower(self):
        from app.services.account_analyzer import score_account
        f = AccountFeatures(
            username="official_account",
            platform="x",
            followers=100000,
            following=500,
            post_count=3000,
            has_profile_pic=True,
            has_bio=True,
            is_verified=True,
            cross_platform_count=3,
        )
        score = score_account(f)
        assert score < 15
