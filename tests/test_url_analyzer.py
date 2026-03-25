"""Tests for ScamRadar URL analyzer."""

import pytest
from app.services.url_analyzer import _extract_domain, _is_official, _check_impersonation, _is_short_url


class TestDomainExtraction:

    def test_basic_url(self):
        assert _extract_domain("https://example.com/path") == "example.com"

    def test_www_stripped(self):
        assert _extract_domain("https://www.google.com") == "google.com"

    def test_subdomain_preserved(self):
        assert _extract_domain("https://api.line.me/v2") == "api.line.me"

    def test_no_scheme(self):
        assert _extract_domain("example.com/page") == "example.com"


class TestOfficialDomains:

    def test_line_official(self):
        assert _is_official("line.me") is True
        assert _is_official("store.line.me") is True

    def test_google_official(self):
        assert _is_official("google.com") is True
        assert _is_official("accounts.google.com") is True

    def test_shopee_official(self):
        assert _is_official("shopee.tw") is True

    def test_gov_tw(self):
        assert _is_official("moi.gov.tw") is True

    def test_fake_not_official(self):
        assert _is_official("line-event-prize.top") is False
        assert _is_official("google-login.xyz") is False


class TestImpersonation:

    def test_line_phishing(self):
        assert _check_impersonation("line-event-prize.top") == "LINE"
        assert _check_impersonation("l1ne-login.com") == "LINE"
        assert _check_impersonation("line-verify.xyz") == "LINE"

    def test_facebook_phishing(self):
        assert _check_impersonation("fb-login-verify.com") == "Facebook"

    def test_google_phishing(self):
        assert _check_impersonation("g00gle-login.com") == "Google"

    def test_no_impersonation(self):
        assert _check_impersonation("mywebsite.com") is None
        assert _check_impersonation("random-blog.net") is None


class TestShortUrls:

    def test_known_shorteners(self):
        assert _is_short_url("bit.ly") is True
        assert _is_short_url("reurl.cc") is True
        assert _is_short_url("tinyurl.com") is True
        assert _is_short_url("t.co") is True

    def test_normal_domains(self):
        assert _is_short_url("google.com") is False
        assert _is_short_url("line.me") is False
