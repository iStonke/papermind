import uuid

from fastapi import APIRouter, Depends, File, Header, Query, Request, status, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import verify_shared_upload_api_key
from app.db import get_db
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
