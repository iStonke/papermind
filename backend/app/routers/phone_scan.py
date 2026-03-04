from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.phone_scan import (
    PhoneScanSessionCreateRequest,
    PhoneScanSessionCreateResponse,
    PhoneScanStatusResponse,
    PhoneScanUploadResponse,
)
from app.services.phone_scan_service import PhoneScanService

router = APIRouter(tags=["Phone Scan"])


@router.post(
    "/api/phone-scan/session",
    response_model=PhoneScanSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create QR session for iPhone photo scan uploads",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_phone_scan_session(
    request: Request,
    payload: PhoneScanSessionCreateRequest | None = None,
    db: Session = Depends(get_db),
) -> PhoneScanSessionCreateResponse:
    service = PhoneScanService(db)
    parsed = payload or PhoneScanSessionCreateRequest()
    return service.create_session(
        request=request,
        max_files=parsed.maxFiles,
        target_stage_id=parsed.stageId,
    )


@router.post(
    "/api/phone-scan/upload",
    response_model=PhoneScanUploadResponse,
    summary="Upload captured phone scan images by token",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
def upload_phone_scan_files(
    request: Request,
    files: list[UploadFile] = File(..., description="Captured image files"),
    meta: str | None = Form(default=None, description="Optional upload metadata JSON"),
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> PhoneScanUploadResponse:
    service = PhoneScanService(db)
    return service.upload_files(token=token, files=files, meta=meta, request=request)


@router.get(
    "/api/phone-scan/status",
    response_model=PhoneScanStatusResponse,
    summary="Read phone scan session status by token",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_phone_scan_status(
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> PhoneScanStatusResponse:
    service = PhoneScanService(db)
    return service.get_status(token=token)
