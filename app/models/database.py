"""SQLAlchemy async models for ScamRadar."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column, BigInteger, String, Text, SmallInteger, Integer, Boolean,
    DateTime, ForeignKey, Index, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    line_user_id = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_active_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    query_count = Column(Integer, default=0)

    queries = relationship("Query", back_populates="user")


class Query(Base):
    __tablename__ = "queries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), index=True)
    query_type = Column(String(20), nullable=False)  # account | content | url | image
    input_text = Column(Text, nullable=False)
    input_type = Column(String(20), nullable=False)  # text | image | postback
    risk_score = Column(SmallInteger)
    risk_level = Column(String(10))  # low | medium | high | critical
    result_json = Column(JSONB, nullable=False, default={})
    analysis_engine = Column(String(20))  # rule | ai | hybrid
    response_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="queries")

    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_risk_score_range"),
        Index("idx_queries_created", "created_at"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(BigInteger, ForeignKey("queries.id"))
    user_id = Column(BigInteger, ForeignKey("users.id"))
    is_helpful = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Report(Base):
    __tablename__ = "reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(BigInteger, ForeignKey("queries.id"))
    reporter_id = Column(BigInteger, ForeignKey("users.id"))
    report_type = Column(String(20), nullable=False)  # scam | impersonation | spam | other
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Blacklist(Base):
    __tablename__ = "blacklist"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    target_type = Column(String(20), nullable=False)  # username | url | domain | phone | line_id
    target_value = Column(String(512), nullable=False)
    platform = Column(String(20))  # instagram | facebook | twitter | line | all
    risk_score = Column(SmallInteger, default=80)
    report_count = Column(Integer, default=1)
    source = Column(String(50))  # user_report | 165_import | auto_detect
    first_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_reported_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("target_type", "target_value", "platform", name="uq_blacklist_target"),
        Index("idx_blacklist_value", "target_value"),
    )


class AccountCache(Base):
    __tablename__ = "account_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(128), nullable=False)
    platform = Column(String(20), nullable=False)
    profile_data = Column(JSONB, nullable=False, default={})
    risk_score = Column(SmallInteger)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=1),
    )

    __table_args__ = (
        UniqueConstraint("username", "platform", name="uq_cache_user_platform"),
        Index("idx_cache_expires", "expires_at"),
    )


# --- Database session factory ---

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=settings.debug)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
