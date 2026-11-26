"""
Rate limiting (tiêu chí 7).
"""
import time
import uuid
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Sliding window 60 giây lưu trong Redis sorted set."""
    now = time.time()
    redis_key = f"ratelimit:{key}"
    window_start = now - WINDOW_SECONDS

    try:
        r.zremrangebyscore(redis_key, "-inf", window_start)
        current_count = r.zcard(redis_key)
        if current_count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
        r.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
        r.expire(redis_key, WINDOW_SECONDS)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")
