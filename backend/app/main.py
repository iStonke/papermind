import asyncio
import contextlib
import logging
import os

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.deps import authenticate_request
from app.core.errors import install_exception_handlers
from app.core.logging import install_query_token_redaction
from app.core.observability import request_metrics_middleware
from app.db.session import SessionLocal
from app.routers import (
    ai_router,
    annotations_router,
    auth_router,
    backup_router,
    categories_router,
    correspondents_router,
    dashboard_router,
    document_types_router,
    documents_router,
    health_router,
    import_router,
    jobs_router,
    retrieval_router,
    retention_router,
    saved_searches_router,
    scanners_router,
    search_events_router,
    settings_router,
    sidebar_router,
    smart_folders_router,
    system_router,
    tags_router,
    users_router,
)
from app.services.users import UserService
from app.services.settings import SettingsService

settings = get_settings()

logger = logging.getLogger("papermind.backend")
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
install_query_token_redaction()

OLLAMA_WARMUP_INTERVAL_SECONDS = 600
_ollama_warmup_task: asyncio.Task | None = None


def _check_db_connection_sync() -> tuple[bool, str]:
    if not settings.sqlalchemy_database_url:
        return False, "DATABASE_URL is not configured"

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # pragma: no cover - startup infra check
        return False, str(exc)


async def _check_db_connection() -> tuple[bool, str]:
    return await asyncio.to_thread(_check_db_connection_sync)


async def _check_ai_connection() -> tuple[bool, str]:
    ai_health_url = f"{settings.ai_base_url.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(ai_health_url)
        if response.status_code == 200:
            return True, "ok"
        return False, f"HTTP {response.status_code}"
    except Exception as exc:  # pragma: no cover - startup infra check
        return False, str(exc)


def _load_ollama_warmup_config_sync() -> dict[str, object] | None:
    try:
        with SessionLocal() as session:
            runtime_settings = SettingsService(session).get_settings().model_dump(mode="json")
    except Exception as exc:  # pragma: no cover - settings DB best effort
        logger.debug("Ollama warmup settings load failed: %s", exc)
        return None
    ollama_cfg = runtime_settings.get("ollama") or {}
    if not ollama_cfg.get("enabled"):
        return None
    return {
        "base_url": str(ollama_cfg.get("base_url") or "http://localhost:11434").rstrip("/"),
        "model": str(ollama_cfg.get("model") or "llama3.2:3b"),
        "timeout_seconds": max(2.0, min(float(ollama_cfg.get("timeout_seconds") or 90.0), 20.0)),
    }


async def _warm_ollama_for_import_analysis_once() -> None:
    cfg = await asyncio.to_thread(_load_ollama_warmup_config_sync)
    if not cfg:
        return
    payload = {
        "model": cfg["model"],
        "stream": False,
        "format": "json",
        "keep_alive": "15m",
        "prompt": 'Antworte nur mit {"status":"ok"}.',
    }
    try:
        async with httpx.AsyncClient(timeout=float(cfg["timeout_seconds"])) as client:
            response = await client.post(f"{cfg['base_url']}/api/generate", json=payload)
        response.raise_for_status()
        logger.debug("Ollama import analysis warmup completed model=%s", cfg["model"])
    except Exception as exc:  # pragma: no cover - optional local service
        logger.debug("Ollama import analysis warmup skipped: %s", exc)


async def _ollama_warmup_loop() -> None:
    await asyncio.sleep(5)
    while True:
        await _warm_ollama_for_import_analysis_once()
        await asyncio.sleep(OLLAMA_WARMUP_INTERVAL_SECONDS)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="PaperMind AP8 API with OCR pipeline, chunking, embeddings (pgvector) and retrieval",
    dependencies=[Depends(authenticate_request)],
    # OpenAPI-Schema/Docs nur, wenn explizit freigegeben (kein offenes Schema in Prod).
    openapi_url="/openapi.json" if settings.expose_api_docs else None,
    docs_url="/docs" if settings.expose_api_docs else None,
    redoc_url="/redoc" if settings.expose_api_docs else None,
)
app.middleware("http")(request_metrics_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_exception_handlers(app)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
# Direkt-Upload (iOS-Shortcut, API-Key) ist mit der Pro-Benutzer-Datentrennung
# vorübergehend deaktiviert, da kein Benutzerkontext zugeordnet werden kann.
# app.include_router(direct_upload_router)
app.include_router(documents_router)
app.include_router(import_router)
app.include_router(tags_router)
app.include_router(annotations_router)
app.include_router(categories_router)
app.include_router(correspondents_router)
app.include_router(document_types_router)
app.include_router(jobs_router)
app.include_router(retrieval_router)
app.include_router(retention_router)
app.include_router(ai_router)
app.include_router(backup_router)
app.include_router(saved_searches_router)
app.include_router(scanners_router)
app.include_router(search_events_router)
app.include_router(smart_folders_router)
app.include_router(settings_router)
app.include_router(sidebar_router)
app.include_router(dashboard_router)
app.include_router(system_router)


def _bootstrap_admin_sync() -> None:
    """Create the initial admin account when the users table is empty."""
    if not settings.auth_enabled:
        return
    if not settings.initial_admin_password.strip():
        return
    try:
        with SessionLocal() as session:
            service = UserService(session)
            if service.count() > 0:
                return
            from app.schemas.users import UserCreateRequest

            service.create_user(
                UserCreateRequest(
                    username=settings.initial_admin_username.strip() or "admin",
                    password=settings.initial_admin_password,
                    is_admin=True,
                )
            )
            logger.info("Bootstrap admin user '%s' created", settings.initial_admin_username)
    except Exception as exc:  # pragma: no cover - startup infra
        logger.error("Bootstrap admin creation failed: %s", exc)


@app.on_event("startup")
async def on_startup() -> None:
    global _ollama_warmup_task
    os.makedirs(settings.storage_path, exist_ok=True)

    db_ok, db_detail = await _check_db_connection()
    if db_ok:
        logger.info("DB startup check passed")
    else:
        logger.error("DB startup check failed: %s", db_detail)

    if not settings.auth_secret_key.strip():
        logger.warning(
            "AUTH_SECRET_KEY is not set — using an ephemeral signing key. "
            "Tokens will be invalidated on restart. Set AUTH_SECRET_KEY in production."
        )
    await asyncio.to_thread(_bootstrap_admin_sync)

    ai_ok, ai_detail = await _check_ai_connection()
    if ai_ok:
        logger.info("AI startup check passed")
    else:
        logger.error("AI startup check failed: %s", ai_detail)

    if _ollama_warmup_task is None or _ollama_warmup_task.done():
        _ollama_warmup_task = asyncio.create_task(_ollama_warmup_loop())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _ollama_warmup_task
    if _ollama_warmup_task is None:
        return
    _ollama_warmup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _ollama_warmup_task
    _ollama_warmup_task = None
