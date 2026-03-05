import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.phone_scan import (
    PhoneScanJobStatusResponse,
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


@router.get(
    "/api/phone-scan/status/{job_id}",
    response_model=PhoneScanJobStatusResponse,
    summary="Read phone scan processing job status",
    responses={404: {"model": ErrorResponse}},
)
def get_phone_scan_job_status(
    job_id: str,
    db: Session = Depends(get_db),
) -> PhoneScanJobStatusResponse:
    service = PhoneScanService(db)
    return service.get_job_status(job_id=job_id)


@router.get(
    "/api/phone-scan/events/{job_id}",
    summary="Stream phone scan job status updates via SSE",
)
async def phone_scan_job_events(
    job_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    service = PhoneScanService(db)
    initial = service.get_job_status(job_id=job_id)

    async def event_stream():
        last_updated = ""
        yield f"data: {json.dumps(initial.model_dump(mode='json'))}\n\n"
        last_updated = initial.updatedAt.isoformat()
        while True:
            payload = service.get_job_status(job_id=job_id)
            marker = payload.updatedAt.isoformat()
            if marker != last_updated:
                yield f"data: {json.dumps(payload.model_dump(mode='json'))}\n\n"
                last_updated = marker
            if payload.state in {"ready", "error"}:
                break
            await asyncio.sleep(0.25)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
