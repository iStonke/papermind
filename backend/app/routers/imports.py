from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, status, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.import_staging import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportInboxClaimRequest,
    ImportInboxClaimResponse,
    ImportInboxListResponse,
    ImportInboxUploadResponse,
    ImportSourceUploadResponse,
)
from app.schemas.import_staging import StageTitleSuggestRequest, StageTitleSuggestResponse
from app.services.import_inbox import ImportInboxService
from app.services.import_staging import ImportStagingService

router = APIRouter(prefix="/api/import", tags=["Import"])
settings = get_settings()


def _verify_inbox_api_key(authorization: str | None = Header(default=None)) -> None:
    configured_key = settings.direct_upload_api_key.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Import inbox is not configured (DIRECT_UPLOAD_API_KEY not set).",
        )
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token.strip() != configured_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key.")


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
) -> ImportSourceUploadResponse:
    service = ImportStagingService(db)
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
    service = ImportInboxService(db)
    return service.upload(files, client_name=x_client_name)


@router.get(
    "/inbox",
    response_model=ImportInboxListResponse,
    summary="List pending Shortcut uploads in the import inbox",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_import_inbox(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ImportInboxListResponse:
    service = ImportInboxService(db)
    return service.list_pending(limit=limit)


@router.post(
    "/inbox/claim",
    response_model=ImportInboxClaimResponse,
    summary="Mark import inbox items as picked up by the web app",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def claim_import_inbox(
    payload: ImportInboxClaimRequest,
    db: Session = Depends(get_db),
) -> ImportInboxClaimResponse:
    service = ImportInboxService(db)
    return service.claim(payload.item_ids)


@router.get(
    "/source/{source_file_id}/file",
    response_class=FileResponse,
    summary="Download staged source PDF",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_import_source_file(source_file_id: str, db: Session = Depends(get_db)) -> FileResponse:
    service = ImportStagingService(db)
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
def commit_import_batch(payload: ImportCommitRequest, db: Session = Depends(get_db)) -> ImportCommitResponse:
    service = ImportStagingService(db)
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
) -> StageTitleSuggestResponse:
    service = ImportStagingService(db)
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
