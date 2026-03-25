"""Report service — saves queries, feedback, reports, and manages blacklist."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.database import (
    User, Query, Feedback, Report, Blacklist,
    get_session_factory,
)
from app.models.schemas import AnalysisResult

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


async def _get_session():
    factory = get_session_factory()
    return factory()


# ============================================================
# User management
# ============================================================

async def get_or_create_user(line_user_id: str, display_name: str = None) -> Optional[int]:
    """Get existing user or create new one. Returns user id."""
    try:
        session = await _get_session()
        async with session:
            result = await session.execute(
                select(User).where(User.line_user_id == line_user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                user.last_active_at = _now()
                user.query_count = (user.query_count or 0) + 1
                if display_name:
                    user.display_name = display_name
                await session.commit()
                return user.id
            else:
                new_user = User(
                    line_user_id=line_user_id,
                    display_name=display_name,
                    query_count=1,
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                return new_user.id
    except Exception as e:
        logger.error(f"Failed to get/create user: {e}")
        return None


# ============================================================
# Query logging
# ============================================================

async def save_query(
    user_id: Optional[int],
    query_type: str,
    input_text: str,
    input_type: str,
    result: AnalysisResult,
    response_time_ms: int = 0,
) -> Optional[int]:
    """Save a query and its result to the database. Returns query id."""
    try:
        session = await _get_session()
        async with session:
            query = Query(
                user_id=user_id,
                query_type=query_type,
                input_text=input_text[:2000],
                input_type=input_type,
                risk_score=result.score,
                risk_level=result.level,
                result_json=result.model_dump(),
                analysis_engine=result.engine,
                response_time_ms=response_time_ms,
            )
            session.add(query)
            await session.commit()
            await session.refresh(query)
            return query.id
    except Exception as e:
        logger.error(f"Failed to save query: {e}")
        return None


# ============================================================
# Feedback
# ============================================================

async def save_feedback(query_id: int, user_id: Optional[int], is_helpful: bool) -> bool:
    """Save user feedback for a query."""
    try:
        session = await _get_session()
        async with session:
            fb = Feedback(
                query_id=query_id,
                user_id=user_id,
                is_helpful=is_helpful,
            )
            session.add(fb)
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        return False


# ============================================================
# Reports + Blacklist
# ============================================================

async def save_report(query_id: int, reporter_id: Optional[int], report_type: str = "scam") -> int:
    """Save a scam report and update the blacklist. Returns total report count for this target."""
    try:
        session = await _get_session()
        async with session:
            # Save the report
            report = Report(
                query_id=query_id,
                reporter_id=reporter_id,
                report_type=report_type,
            )
            session.add(report)

            # Get the original query to find what was reported
            result = await session.execute(
                select(Query).where(Query.id == query_id)
            )
            query = result.scalar_one_or_none()

            report_count = 1
            if query:
                target_type, target_value = _extract_target(query)
                if target_type and target_value:
                    report_count = await _update_blacklist(
                        session, target_type, target_value, query.query_type
                    )

            await session.commit()
            return report_count
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        return 0


def _extract_target(query: Query) -> tuple[Optional[str], Optional[str]]:
    """Extract the blacklist target from a query."""
    input_text = query.input_text.strip()
    query_type = query.query_type

    if query_type == "account":
        return "username", input_text.lstrip("@")
    elif query_type == "url":
        return "url", input_text
    elif query_type == "phone":
        return "phone", input_text
    elif query_type == "content":
        # For content, blacklist the text hash (first 200 chars as identifier)
        return "content", input_text[:200]
    elif query_type == "image":
        return "content", input_text[:200] if input_text else None

    return None, None


async def _update_blacklist(
    session, target_type: str, target_value: str, platform: str = "all"
) -> int:
    """Insert or update blacklist entry. Returns new report count."""
    try:
        # Try to find existing entry
        result = await session.execute(
            select(Blacklist).where(
                Blacklist.target_type == target_type,
                Blacklist.target_value == target_value,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.report_count = (existing.report_count or 0) + 1
            existing.last_reported_at = _now()
            # Increase risk score based on reports
            new_score = min(100, (existing.risk_score or 50) + 5)
            existing.risk_score = new_score
            return existing.report_count
        else:
            new_entry = Blacklist(
                target_type=target_type,
                target_value=target_value,
                platform=platform,
                risk_score=60,
                report_count=1,
                source="user_report",
            )
            session.add(new_entry)
            return 1
    except Exception as e:
        logger.error(f"Failed to update blacklist: {e}")
        return 1


# ============================================================
# Blacklist queries (used by analyzers)
# ============================================================

async def check_blacklist(target_type: str, target_value: str) -> Optional[dict]:
    """Check if a target is in the blacklist. Returns blacklist info or None."""
    try:
        session = await _get_session()
        async with session:
            result = await session.execute(
                select(Blacklist).where(
                    Blacklist.target_type == target_type,
                    Blacklist.target_value == target_value,
                )
            )
            entry = result.scalar_one_or_none()

            if entry:
                return {
                    "target_type": entry.target_type,
                    "target_value": entry.target_value,
                    "risk_score": entry.risk_score,
                    "report_count": entry.report_count,
                    "source": entry.source,
                    "first_seen": entry.first_seen_at.isoformat() if entry.first_seen_at else None,
                    "last_reported": entry.last_reported_at.isoformat() if entry.last_reported_at else None,
                }
            return None
    except Exception as e:
        logger.error(f"Failed to check blacklist: {e}")
        return None


async def get_report_count(target_type: str, target_value: str) -> int:
    """Get the number of reports for a target."""
    try:
        session = await _get_session()
        async with session:
            result = await session.execute(
                select(Blacklist.report_count).where(
                    Blacklist.target_type == target_type,
                    Blacklist.target_value == target_value,
                )
            )
            count = result.scalar_one_or_none()
            return count or 0
    except Exception as e:
        logger.error(f"Failed to get report count: {e}")
        return 0
