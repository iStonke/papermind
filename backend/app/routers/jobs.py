import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.jobs import (
    JobActivityBackup,
    JobActivityItem,
    JobActivityResponse,
    JobActivitySummary,
    JobCreateRequest,
    JobListResponse,
    JobRead,
    JobUpdateRequest,
    OcrBacklog,
)
from app.services.jobs import JobService

router = APIRouter(prefix="/api", tags=["Jobs"])


@router.get(
    "/jobs/activity",
    response_model=JobActivityResponse,
    summary="Active and recently failed jobs across all documents (header activity indicator)",
)
def get_job_activity(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobActivityResponse:
    service = JobService(db, user.id)
    result = service.get_activity()
    items = []
    for entry in result["jobs"]:
        item = JobActivityItem.model_validate(entry["job"], from_attributes=True)
        item.document_title = entry["document_title"]
        items.append(item)
    return JobActivityResponse(
        summary=JobActivitySummary(**result["summary"]),
        jobs=items,
        ocr_backlog=OcrBacklog(**result["ocr_backlog"]),
        backup=JobActivityBackup(**result["backup"]) if result.get("backup") else None,
    )


@router.get(
    "/documents/{document_id}/jobs",
    response_model=JobListResponse,
    summary="List jobs for a document",
    responses={404: {"model": ErrorResponse}},
)
def list_document_jobs(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobListResponse:
    service = JobService(db, user.id)
    jobs = service.list_document_jobs(document_id)
    return JobListResponse(items=[JobRead.model_validate(job, from_attributes=True) for job in jobs])


@router.post(
    "/documents/{document_id}/jobs",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job for a document",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_document_job(
    document_id: uuid.UUID,
    payload: JobCreateRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> JobRead:
    service = JobService(db, user.id)
    return JobRead.model_validate(service.create_document_job(document_id, payload), from_attributes=True)


@router.patch(
    "/jobs/{job_id}",
    response_model=JobRead,
    summary="Update job status/progress",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_job(job_id: uuid.UUID, payload: JobUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    service = JobService(db, user.id)
    return JobRead.model_validate(service.update_job(job_id, payload), from_attributes=True)


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss a finished/failed job from the activity feed",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def dismiss_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    JobService(db, user.id).dismiss_job(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/jobs/activity/dismiss-failed",
    summary="Dismiss all failed jobs from the activity feed",
)
def dismiss_failed_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    removed = JobService(db, user.id).dismiss_failed_jobs()
    return {"removed": removed}
