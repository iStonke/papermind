from fastapi import APIRouter, Depends, File, status, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.import_staging import ImportCommitRequest, ImportCommitResponse, ImportSourceUploadResponse
from app.schemas.import_staging import StageTitleSuggestRequest, StageTitleSuggestResponse
from app.services.import_staging import ImportStagingService

router = APIRouter(prefix="/api/import", tags=["Import"])


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
