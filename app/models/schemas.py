"""Pydantic schemas for ScamRadar API."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Unified analysis result returned by all engines."""
    id: Optional[int] = None
    query_type: str  # account | content | url
    score: int = Field(ge=0, le=100)
    level: str  # low | medium | high | critical
    flags: list[str] = []
    explanation: str = ""
    action: str = ""
    scam_type: Optional[str] = None
    details: dict = {}
    engine: str = "rule"  # rule | ai | hybrid


class AccountFeatures(BaseModel):
    """Features extracted from social media profile."""
    username: str
    platform: str
    account_age_days: Optional[int] = None
    followers: int = 0
    following: int = 0
    post_count: int = 0
    has_profile_pic: bool = False
    has_bio: bool = False
    is_verified: bool = False
    bio_text: str = ""
    engagement_rate: float = 0.0
    cross_platform_count: int = 0
    in_blacklist: bool = False
    report_count: int = 0


class UrlCheckResult(BaseModel):
    """Result from URL safety analysis."""
    url: str
    is_safe: bool
    domain: str
    domain_age_days: Optional[int] = None
    is_blacklisted: bool = False
    is_impersonation: bool = False
    impersonated_brand: Optional[str] = None
    expanded_url: Optional[str] = None  # for short URLs
    flags: list[str] = []


class ContentFlag(BaseModel):
    """Single flag from rule engine or AI analysis."""
    label: str
    score: int
    scam_type: str
    severity: str  # low | medium | high | critical


class RuleEngineResult(BaseModel):
    """Result from keyword/regex rule engine."""
    score: int = 0
    flags: list[ContentFlag] = []


class UserProfile(BaseModel):
    """LINE user profile info."""
    line_user_id: str
    display_name: Optional[str] = None
    query_count: int = 0
    created_at: Optional[datetime] = None
