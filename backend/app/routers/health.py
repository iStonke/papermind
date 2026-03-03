import asyncio

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal

router = APIRouter(tags=["Health"])
settings = get_settings()


def _check_db_sync() -> tuple[bool, str]:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # pragma: no cover - infra check
        return False, str(exc)


async def _check_db() -> tuple[bool, str]:
    return await asyncio.to_thread(_check_db_sync)


async def _check_ai() -> tuple[bool, str]:
    url = f"{settings.ai_base_url.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
        if response.status_code == 200:
            return True, "ok"
        return False, f"HTTP {response.status_code}"
    except Exception as exc:  # pragma: no cover - infra check
        return False, str(exc)


@router.get("/health", summary="Service health")
async def health() -> dict:
    db_ok, db_detail = await _check_db()
    ai_ok, ai_detail = await _check_ai()
    status = "ok" if db_ok and ai_ok else "degraded"

    return {
        "status": status,
        "service": "backend",
        "checks": {
            "database": {"ok": db_ok, "detail": db_detail},
            "ai": {"ok": ai_ok, "detail": ai_detail},
        },
    }
