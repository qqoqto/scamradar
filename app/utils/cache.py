"""Redis cache utility for ScamRadar."""

import json
import logging
from typing import Optional
import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Optional[dict]:
    try:
        r = await get_redis()
        data = await r.get(f"scamradar:{key}")
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Cache get failed for {key}: {e}")
    return None


async def cache_set(key: str, value: dict, ttl: int = 3600) -> None:
    try:
        r = await get_redis()
        await r.setex(f"scamradar:{key}", ttl, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Cache set failed for {key}: {e}")


async def cache_delete(key: str) -> None:
    try:
        r = await get_redis()
        await r.delete(f"scamradar:{key}")
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")
