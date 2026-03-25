"""
ScamRadar Phase 2 — Public API
Routes: /api/v1/public/...

Integrates with Phase 1 services (content_analyzer, account_analyzer,
url_analyzer, phone_analyzer) which all return AnalysisResult.
"""

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
import time
import logging

router = APIRouter(prefix="/api/v1/public", tags=["public"])
logger = logging.getLogger(__name__)


# ─── Request / Response schemas ─────────────────────────────────

class CheckPhoneRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20, examples=["+886912345678"])

class CheckUrlRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2048, examples=["https://example.com"])

class CheckUsernameRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100, examples=["@scammer123"])

class CheckContentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

class CheckResponse(BaseModel):
    risk_level: str       # low / medium / high / critical
    risk_score: int       # 0-100
    summary: str          # explanation text
    action: str           # suggested action
    flags: list[str]      # flag labels
    details: dict         # extra details
    engine: str           # rule / ai / hybrid
    cached: bool = False
    timestamp: str

class StatsResponse(BaseModel):
    total_queries: int
    total_users: int
    total_reports: int
    total_blacklisted: int
    queries_today: int
    queries_this_week: int
    top_risk_categories: list
    risk_distribution: dict
    daily_trend: list

class BlacklistEntry(BaseModel):
    target_type: str        # username / url / domain / phone / line_id
    target_value: str
    platform: Optional[str] = None
    risk_score: int
    report_count: int
    source: Optional[str] = None
    last_reported: str


# ─── Rate limiting (in-memory, per-IP) ──────────────────────────

_rate_limits: dict = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 20     # requests per window per IP


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    if client_ip not in _rate_limits:
        _rate_limits[client_ip] = []
    _rate_limits[client_ip] = [t for t in _rate_limits[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limits[client_ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limits[client_ip].append(now)
    return True


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ensure_rate_limit(request: Request):
    if not _check_rate_limit(_get_client_ip(request)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. 每分鐘最多 20 次查詢。")


# ─── Helper: AnalysisResult → CheckResponse ─────────────────────

def _to_check_response(result, cached: bool = False) -> CheckResponse:
    """Convert Phase 1 AnalysisResult to Phase 2 API response."""
    return CheckResponse(
        risk_level=result.level,
        risk_score=result.score,
        summary=result.explanation,
        action=result.action,
        flags=result.flags,
        details=result.details,
        engine=result.engine,
        cached=cached,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─── Helper: Log query to DB (best-effort) ──────────────────────

async def _log_query(query_type: str, input_text: str, result):
    """Log API query to database (non-blocking, best-effort)."""
    try:
        from app.models.database import get_session_factory, Query as QueryModel
        factory = get_session_factory()
        async with factory() as session:
            q = QueryModel(
                query_type=query_type,
                input_text=input_text[:2000],
                input_type="text",
                risk_score=result.score,
                risk_level=result.level,
                result_json={
                    "flags": result.flags,
                    "engine": result.engine,
                    "source": "web_api",
                },
                analysis_engine=result.engine,
            )
            session.add(q)
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to log API query: {e}")


# ─── Check endpoints ────────────────────────────────────────────

@router.post("/check/phone", response_model=CheckResponse)
async def check_phone(body: CheckPhoneRequest, request: Request):
    """檢查電話號碼的詐騙風險。"""
    _ensure_rate_limit(request)
    from app.services.phone_analyzer import analyze_phone
    result = await analyze_phone(body.phone)
    await _log_query("phone", body.phone, result)
    return _to_check_response(result)


@router.post("/check/url", response_model=CheckResponse)
async def check_url(body: CheckUrlRequest, request: Request):
    """檢查網址連結是否安全。"""
    _ensure_rate_limit(request)
    from app.services.url_analyzer import analyze_url
    result = await analyze_url(body.url)
    await _log_query("url", body.url[:500], result)
    return _to_check_response(result)


@router.post("/check/username", response_model=CheckResponse)
async def check_username(body: CheckUsernameRequest, request: Request):
    """分析社群帳號的可信度。"""
    _ensure_rate_limit(request)
    from app.services.account_analyzer import analyze_account
    result = await analyze_account(body.username)
    await _log_query("account", body.username, result)
    return _to_check_response(result)


@router.post("/check/content", response_model=CheckResponse)
async def check_content(body: CheckContentRequest, request: Request):
    """分析文字訊息的詐騙特徵。"""
    _ensure_rate_limit(request)
    from app.services.content_analyzer import analyze_content
    result = await analyze_content(body.content)
    await _log_query("content", body.content[:500], result)
    return _to_check_response(result)


# ─── Stats endpoint ─────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """取得 ScamRadar 全站統計資料。"""
    from app.models.database import get_session_factory, Query as QueryModel, User, Report, Blacklist
    from sqlalchemy import select, func

    factory = get_session_factory()
    async with factory() as session:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())

        total_queries = (await session.execute(select(func.count(QueryModel.id)))).scalar() or 0
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        total_reports = (await session.execute(select(func.count(Report.id)))).scalar() or 0
        total_blacklisted = (await session.execute(select(func.count(Blacklist.id)))).scalar() or 0

        queries_today = (await session.execute(
            select(func.count(QueryModel.id)).where(QueryModel.created_at >= today_start)
        )).scalar() or 0

        queries_this_week = (await session.execute(
            select(func.count(QueryModel.id)).where(QueryModel.created_at >= week_start)
        )).scalar() or 0

        # Risk distribution
        risk_rows = (await session.execute(
            select(QueryModel.risk_level, func.count(QueryModel.id))
            .group_by(QueryModel.risk_level)
        )).all()
        risk_distribution = {row[0]: row[1] for row in risk_rows if row[0]}

        # Top query types
        cat_rows = (await session.execute(
            select(QueryModel.query_type, func.count(QueryModel.id))
            .group_by(QueryModel.query_type)
            .order_by(func.count(QueryModel.id).desc())
            .limit(5)
        )).all()
        top_risk_categories = [{"category": row[0], "count": row[1]} for row in cat_rows]

        # Daily trend (last 14 days)
        daily_trend = []
        for i in range(13, -1, -1):
            day = today_start - timedelta(days=i)
            next_day = day + timedelta(days=1)
            count = (await session.execute(
                select(func.count(QueryModel.id)).where(
                    QueryModel.created_at >= day,
                    QueryModel.created_at < next_day,
                )
            )).scalar() or 0
            daily_trend.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    return StatsResponse(
        total_queries=total_queries,
        total_users=total_users,
        total_reports=total_reports,
        total_blacklisted=total_blacklisted,
        queries_today=queries_today,
        queries_this_week=queries_this_week,
        top_risk_categories=top_risk_categories,
        risk_distribution=risk_distribution,
        daily_trend=daily_trend,
    )


# ─── Blacklist endpoint ─────────────────────────────────────────

@router.get("/blacklist/top")
async def get_blacklist_top(
    limit: int = Query(default=20, ge=1, le=100),
    type: Optional[str] = Query(default=None, description="Filter: phone, url, username, domain"),
):
    """取得黑名單排行榜（依回報數排序）。"""
    from app.models.database import get_session_factory, Blacklist
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(Blacklist).order_by(Blacklist.report_count.desc())
        if type:
            stmt = stmt.where(Blacklist.target_type == type)
        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return [
        BlacklistEntry(
            target_type=row.target_type,
            target_value=row.target_value,
            platform=row.platform,
            risk_score=row.risk_score or 0,
            report_count=row.report_count or 0,
            source=row.source,
            last_reported=row.last_reported_at.isoformat() if row.last_reported_at else "",
        )
        for row in rows
    ]


# ─── Recent queries (for dashboard history) ─────────────────────

@router.get("/queries/recent")
async def get_recent_queries(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    type: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
):
    """取得近期查詢紀錄。"""
    from app.models.database import get_session_factory, Query as QueryModel
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(QueryModel).order_by(QueryModel.created_at.desc())
        if type:
            stmt = stmt.where(QueryModel.query_type == type)
        if risk_level:
            stmt = stmt.where(QueryModel.risk_level == risk_level)
        stmt = stmt.offset(offset).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "id": row.id,
            "query_type": row.query_type,
            "query_input": (row.input_text or "")[:100],
            "risk_level": row.risk_level,
            "risk_score": row.risk_score,
            "engine": row.analysis_engine,
            "source": (row.result_json or {}).get("source", "line"),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]
