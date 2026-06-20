import asyncio

import httpx
from fastapi import APIRouter, status as http_status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AppSessionLocal

router = APIRouter(tags=["Health"])
settings = get_settings()


def _check_db_sync() -> tuple[bool, str]:
    try:
        with AppSessionLocal() as session:
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


@router.get("/health/live", summary="Process liveness")
async def liveness() -> dict:
    return {"status": "ok", "service": "backend"}


async def _readiness_payload() -> tuple[dict, int]:
    (db_ok, db_detail), (ai_ok, ai_detail) = await asyncio.gather(_check_db(), _check_ai())
    readiness_status = "ok" if db_ok and ai_ok else "degraded"
    payload = {
        "status": readiness_status,
        "service": "backend",
        "checks": {
            "database": {"ok": db_ok, "detail": db_detail},
            "ai": {"ok": ai_ok, "detail": ai_detail},
        },
    }
    status_code = (
        http_status.HTTP_200_OK
        if db_ok and ai_ok
        else http_status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return payload, status_code


@router.get("/health/ready", summary="Service readiness")
async def readiness() -> JSONResponse:
    payload, status_code = await _readiness_payload()
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/health", summary="Service readiness (compatibility alias)")
async def health() -> JSONResponse:
    payload, status_code = await _readiness_payload()
    return JSONResponse(content=payload, status_code=status_code)
