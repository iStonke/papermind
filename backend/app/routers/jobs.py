import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.jobs import (
    JobActivityItem,
    JobActivityResponse,
    JobActivitySummary,
    JobCreateRequest,
    JobListResponse,
    JobRead,
    JobUpdateRequest,
)
from app.services.jobs import JobService

router = APIRouter(prefix="/api", tags=["Jobs"])


@router.get(
    "/jobs/activity",
    response_model=JobActivityResponse,
    summary="Active and recently failed jobs across all documents (header activity indicator)",
)
def get_job_activity(db: Session = Depends(get_db)) -> JobActivityResponse:
    service = JobService(db)
    result = service.get_activity()
    items = []
    for entry in result["jobs"]:
        item = JobActivityItem.model_validate(entry["job"], from_attributes=True)
        item.document_title = entry["document_title"]
        items.append(item)
    return JobActivityResponse(
        summary=JobActivitySummary(**result["summary"]),
        jobs=items,
    )


@router.get(
    "/documents/{document_id}/jobs",
    response_model=JobListResponse,
    summary="List jobs for a document",
    responses={404: {"model": ErrorResponse}},
)
def list_document_jobs(document_id: uuid.UUID, db: Session = Depends(get_db)) -> JobListResponse:
    service = JobService(db)
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
    db: Session = Depends(get_db),
) -> JobRead:
    service = JobService(db)
    return JobRead.model_validate(service.create_document_job(document_id, payload), from_attributes=True)


@router.patch(
    "/jobs/{job_id}",
    response_model=JobRead,
    summary="Update job status/progress",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_job(job_id: uuid.UUID, payload: JobUpdateRequest, db: Session = Depends(get_db)) -> JobRead:
    service = JobService(db)
    return JobRead.model_validate(service.update_job(job_id, payload), from_attributes=True)
