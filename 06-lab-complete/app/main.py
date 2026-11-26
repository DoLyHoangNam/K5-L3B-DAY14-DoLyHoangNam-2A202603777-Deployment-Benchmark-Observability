"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Định dạng mọi dòng log của app thành 1 JSON object hợp lệ."""

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        try:
            parsed = json.loads(msg)
            if isinstance(parsed, dict):
                payload = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "lvl": record.levelname,
                    "logger": record.name,
                    **parsed,
                }
                return json.dumps(payload, ensure_ascii=False)
        except Exception:
            pass
        return json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "lvl": record.levelname,
                "logger": record.name,
                "msg": msg,
            },
            ensure_ascii=False,
        )


logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(JsonFormatter())
    logger.addHandler(_handler)

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        json.dumps(
            {
                "event": "startup",
                "environment": settings.environment,
                "port": settings.port,
            }
        )
    )
    yield
    logger.info(json.dumps({"event": "shutdown", "status": "completed"}))


app = FastAPI(title="Production AI Agent", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    """Liveness probe: luôn trả 200 khi process còn chạy."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    """Readiness probe: 200 khi Redis sẵn sàng, 503 khi mất kết nối."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis is not ready")
    return {"status": "ready", "redis": "connected"}


@app.post("/ask")
def ask(
    body: AskRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    started = time.time()
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    cost_usd = record_cost(input_tokens, output_tokens)
    latency_ms = round((time.time() - started) * 1000, 2)

    logger.info(
        json.dumps(
            {
                "event": "ask",
                "path": "/ask",
                "status": 200,
                "ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            }
        )
    )
    return {
        "question": body.question,
        "answer": answer,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        },
    }


_previous_sigterm = signal.getsignal(signal.SIGTERM)


def _on_sigterm(signum, frame):
    logger.info(json.dumps({"event": "sigterm_received", "signal": signum}))
    if callable(_previous_sigterm):
        _previous_sigterm(signum, frame)


signal.signal(signal.SIGTERM, _on_sigterm)
