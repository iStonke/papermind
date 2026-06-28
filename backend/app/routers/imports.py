import asyncio
import hashlib
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, File, Header, Query, Request, status, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import verify_shared_upload_api_key
from app.db import get_db
from app.db.session import AppSessionLocal
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.import_staging import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportInboxAssignRequest,
    ImportInboxAssignResponse,
    ImportInboxClaimRequest,
    ImportInboxClaimResponse,
    ImportInboxDiscardPagesRequest,
    ImportInboxDiscardPagesResponse,
    ImportInboxDiscardRequest,
    ImportInboxDiscardResponse,
    ImportInboxListResponse,
    ImportInboxUploadResponse,
    ImportSourceUploadResponse,
)
from app.schemas.import_staging import StageTitleSuggestRequest, StageTitleSuggestResponse
from app.services.import_inbox import ImportInboxService
from app.services.import_staging import ImportStagingService

router = APIRouter(prefix="/api/import", tags=["Import"])
settings = get_settings()
logger = logging.getLogger("papermind.import")

# Server-seitiges Poll-Intervall des SSE-Streams. Der Client hält EINE offene
# Verbindung und bekommt Änderungen gepusht; sein eigenes Polling ist nur noch
# Fallback. Die DB-Abfrage ist günstig (indizierte Owner-Query), das Intervall
# bestimmt also nur, wie schnell ein Scan-Statuswechsel beim Client ankommt.
SSE_POLL_INTERVAL_SECONDS = 1.5
# Kommentar-Heartbeat, damit Proxys (Caddy) die Leerlaufverbindung nicht kappen.
SSE_HEARTBEAT_SECONDS = 20.0


def _load_inbox_payload(owner_id: uuid.UUID) -> dict:
    """Inbox-Status für einen Benutzer laden (eigene RLS-Session pro Aufruf).

    Läuft in einem Thread, daher eine kurzlebige Session statt der request-
    gebundenen - sonst bliebe für die Lebensdauer des Streams eine Verbindung
    belegt. owner_id wird für die RLS-Policy gesetzt (siehe db/session.py)."""
    db = AppSessionLocal()
    try:
        db.info["owner_id"] = str(owner_id)
        result = ImportInboxService(db, owner_id).list_pending(limit=50)
        return result.model_dump(mode="json")
    finally:
        db.close()


def _verify_inbox_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    verify_shared_upload_api_key(
        request,
        authorization,
        service_name="Import inbox",
        rate_limit_bucket="import_inbox",
    )


@router.post(
    "/source",
    response_model=ImportSourceUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload source PDFs into import staging",
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def upload_import_sources(
    files: list[UploadFile] = File(..., description="PDF files"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportSourceUploadResponse:
    service = ImportStagingService(db, user.id)
    return service.upload_sources(files)


@router.post(
    "/inbox",
    response_model=ImportInboxUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Shortcut PDFs into the import inbox",
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def upload_import_inbox(
    files: list[UploadFile] = File(..., description="PDF files"),
    x_client_name: str | None = Header(default=None, alias="X-Client-Name"),
    db: Session = Depends(get_db),
    _: None = Depends(_verify_inbox_api_key),
) -> ImportInboxUploadResponse:
    # Vorübergehend deaktiviert: maschinelle Importe ohne Benutzerkontext sind
    # mit der Pro-Benutzer-Datentrennung nicht zuordenbar.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Der Inbox-Upload ist mit der Pro-Benutzer-Trennung vorübergehend deaktiviert.",
    )


@router.get(
    "/inbox",
    response_model=ImportInboxListResponse,
    summary="List pending Shortcut uploads in the import inbox",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_import_inbox(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportInboxListResponse:
    service = ImportInboxService(db, user.id)
    return service.list_pending(limit=limit)


@router.get(
    "/inbox/events",
    summary="Server-Sent Events stream of import inbox / scan job changes",
    responses={401: {"model": ErrorResponse}},
)
async def stream_import_inbox_events(
    request: Request,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Pusht den Inbox-/Scan-Job-Status als Server-Sent Events.

    Der Client abonniert diesen Stream und braucht dann nicht mehr selbst zu
    pollen (Polling bleibt nur Fallback). Es werden nur tatsächliche Änderungen
    gesendet (Hash-Vergleich) plus gelegentliche Heartbeats.
    """
    owner_id = user.id

    async def event_stream():
        last_digest: str | None = None
        last_emit = time.monotonic()
        # Stream sofort öffnen, damit der Browser die Verbindung als etabliert
        # ansieht, bevor die erste Inbox-Abfrage durch ist.
        yield ": connected\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.to_thread(_load_inbox_payload, owner_id)
            except Exception:  # noqa: BLE001 - transienter DB-Fehler darf den Stream nicht abreißen
                logger.exception("inbox sse payload load failed owner_id=%s", owner_id)
                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
                continue
            payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)
            digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            now = time.monotonic()
            if digest != last_digest:
                last_digest = digest
                last_emit = now
                yield f"event: inbox\ndata: {payload_json}\n\n"
            elif now - last_emit >= SSE_HEARTBEAT_SECONDS:
                last_emit = now
                yield ": keepalive\n\n"
            await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            # nginx/Caddy davon abhalten, den Stream zu puffern.
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/inbox/assign",
    response_model=ImportInboxAssignResponse,
    summary="Assign visible scanner inbox items to the current user",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def assign_import_inbox(
    payload: ImportInboxAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportInboxAssignResponse:
    service = ImportInboxService(db, user.id)
    return service.assign_to_current_user(payload.item_ids)


@router.post(
    "/inbox/claim",
    response_model=ImportInboxClaimResponse,
    summary="Mark import inbox items as picked up by the web app",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def claim_import_inbox(
    payload: ImportInboxClaimRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportInboxClaimResponse:
    service = ImportInboxService(db, user.id)
    return service.claim(payload.item_ids)


@router.post(
    "/inbox/discard",
    response_model=ImportInboxDiscardResponse,
    summary="Discard import inbox items and delete staged source PDFs",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def discard_import_inbox(
    payload: ImportInboxDiscardRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportInboxDiscardResponse:
    service = ImportInboxService(db, user.id)
    return service.discard(payload.item_ids)


@router.post(
    "/inbox/source/{source_file_id}/pages/discard",
    response_model=ImportInboxDiscardPagesResponse,
    summary="Discard pages from an import inbox source PDF",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def discard_import_inbox_source_pages(
    source_file_id: uuid.UUID,
    payload: ImportInboxDiscardPagesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportInboxDiscardPagesResponse:
    service = ImportInboxService(db, user.id)
    return service.discard_pages(source_file_id, payload.page_indices)


@router.get(
    "/source/{source_file_id}/file",
    response_class=FileResponse,
    summary="Download staged source PDF",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_import_source_file(
    source_file_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    service = ImportStagingService(db, user.id)
    source_path = service.get_source_pdf_path(source_file_id)
    return FileResponse(
        path=str(source_path),
        media_type="application/pdf",
        filename=f"{source_file_id}.pdf",
    )


@router.post(
    "/commit",
    response_model=ImportCommitResponse,
    summary="Commit staged import documents",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def commit_import_batch(
    payload: ImportCommitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportCommitResponse:
    service = ImportStagingService(db, user.id)
    return service.commit(payload)


@router.post(
    "/stages/{stage_id}/suggest-title",
    response_model=StageTitleSuggestResponse,
    summary="Suggest a stage title for scan uploads",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def suggest_import_stage_title(
    stage_id: str,
    payload: StageTitleSuggestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StageTitleSuggestResponse:
    service = ImportStagingService(db, user.id)
    result = service.suggest_stage_title(
        payload.sourceFileIds,
        page_scope=payload.pageScope,
        stage_id=stage_id,
    )
    return StageTitleSuggestResponse(
        suggestion=str(result.get("suggestion") or "").strip(),
        status=str(result.get("status") or "ready").strip() or "ready",
        pageScope=payload.pageScope,
        usedFallback=bool(result.get("used_fallback", False)),
        meta=dict(result.get("meta") or {}),
    )
