from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import Engine

request_logger = logging.getLogger("papermind.requests")
query_logger = logging.getLogger("papermind.slow_query")


async def request_metrics_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip()[:128] or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
    if not request.url.path.startswith("/health"):
        request_logger.info(
            "request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
    return response


def install_slow_query_logging(engine: Engine, threshold_ms: int) -> None:
    if threshold_ms <= 0 or getattr(engine, "_papermind_slow_query_logging", False):
        return
    engine._papermind_slow_query_logging = True

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_started_at", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get("query_started_at")
        if not starts:
            return
        duration_ms = (time.perf_counter() - starts.pop()) * 1000
        if duration_ms < threshold_ms:
            return
        operation = str(statement).lstrip().split(None, 1)[0].upper() if statement else "UNKNOWN"
        query_logger.warning(
            "slow_query operation=%s duration_ms=%.1f executemany=%s",
            operation,
            duration_ms,
            bool(executemany),
        )
