import asyncio
import logging
import os

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.deps import authenticate_request
from app.core.errors import install_exception_handlers
from app.db.session import SessionLocal
from app.routers import (
    ai_router,
    auth_router,
    backup_router,
    categories_router,
    correspondents_router,
    document_types_router,
    documents_router,
    health_router,
    import_router,
    jobs_router,
    retrieval_router,
    saved_searches_router,
    settings_router,
    sidebar_router,
    smart_folders_router,
    system_router,
    tags_router,
    users_router,
)
from app.services.users import UserService

settings = get_settings()

logger = logging.getLogger("papermind.backend")
logging.basicConfig(level=logging.INFO)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
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
app.include_router(categories_router)
app.include_router(correspondents_router)
app.include_router(document_types_router)
app.include_router(jobs_router)
app.include_router(retrieval_router)
app.include_router(ai_router)
app.include_router(backup_router)
app.include_router(saved_searches_router)
app.include_router(smart_folders_router)
app.include_router(settings_router)
app.include_router(sidebar_router)
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
