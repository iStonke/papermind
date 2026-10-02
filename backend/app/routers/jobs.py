import uuid

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db import get_db
from app.models.note import Note
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
    NoteAudioExportCreateRequest,
    NoteAudioExportRead,
    OcrBacklog,
)
from app.services.jobs import JobService
from app.services.note_audio_jobs import note_audio_jobs

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
        background=_background_activity(db, user),
        summary=JobActivitySummary(**result["summary"]),
        jobs=items,
        audio_exports=[NoteAudioExportRead.model_validate(item) for item in note_audio_jobs.activity(user.id)],
        ocr_backlog=OcrBacklog(**result["ocr_backlog"]),
        backup=JobActivityBackup(**result["backup"]) if result.get("backup") else None,
    )


@router.post(
    "/notes/{note_id}/audio-exports",
    response_model=NoteAudioExportRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a persistent local Piper audio export for a note",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_note_audio_export(
    note_id: uuid.UUID,
    payload: NoteAudioExportCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteAudioExportRead:
    note_exists = db.execute(
        select(Note.id).where(Note.id == note_id, Note.owner_id == user.id, Note.is_deleted.is_(False))
    ).scalar_one_or_none()
    if note_exists is None:
        raise NotFoundError("Notiz nicht gefunden")
    job = note_audio_jobs.create(
        owner_id=user.id,
        note_id=note_id,
        note_title=payload.title,
        text=payload.text,
        voice=payload.voice,
        language_mode=payload.language_mode,
    )
    if job.get("status") != "queued":
        raise ConflictError("Für diese Notiz läuft bereits ein Audioexport.")
    return NoteAudioExportRead.model_validate(job)


@router.get(
    "/note-audio-jobs/{job_id}/download",
    response_class=FileResponse,
    summary="Download a completed note audio export",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def download_note_audio_export(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> FileResponse:
    job = note_audio_jobs.get(job_id, owner_id=user.id)
    if job is None:
        raise NotFoundError("Audioexport nicht gefunden")
    if job.get("status") != "done":
        raise BadRequestError("Der Audioexport ist noch nicht fertig.")
    path = note_audio_jobs.output_path(job_id)
    if not path.is_file():
        raise NotFoundError("Audiodatei nicht gefunden")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=str(job.get("filename") or "Notiz.wav"),
        headers={"Cache-Control": "private, no-store"},
    )


@router.post(
    "/note-audio-jobs/{job_id}/downloaded",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm that a completed note audio export was downloaded",
    responses={400: {"model": ErrorResponse}},
)
def confirm_note_audio_export_download(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> Response:
    if not note_audio_jobs.acknowledge_download(job_id, user.id):
        raise BadRequestError("Der Audioexport kann nicht abgeschlossen werden.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/note-audio-jobs/{job_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a queued or running note audio export",
)
def cancel_note_audio_export(job_id: uuid.UUID, user: User = Depends(get_current_user)) -> Response:
    if not note_audio_jobs.cancel(job_id, user.id):
        raise BadRequestError("Der Audioexport kann nicht mehr abgebrochen werden.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/note-audio-jobs/{job_id}/retry",
    response_model=NoteAudioExportRead,
    summary="Retry a failed note audio export",
)
def retry_note_audio_export(job_id: uuid.UUID, user: User = Depends(get_current_user)) -> NoteAudioExportRead:
    job = note_audio_jobs.retry(job_id, user.id)
    if job is None:
        raise BadRequestError("Der Audioexport kann nicht erneut gestartet werden.")
    return NoteAudioExportRead.model_validate(job)


@router.delete(
    "/note-audio-jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss a completed or failed note audio export",
)
def dismiss_note_audio_export(job_id: uuid.UUID, user: User = Depends(get_current_user)) -> Response:
    if not note_audio_jobs.dismiss(job_id, user.id):
        raise BadRequestError("Der Audioexport kann nicht entfernt werden.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
def cancel_document_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    return JobRead.model_validate(JobService(db, user.id).control_job(job_id, action="cancel"), from_attributes=True)


@router.post("/jobs/{job_id}/restart", response_model=JobRead)
def restart_document_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    return JobRead.model_validate(JobService(db, user.id).control_job(job_id, action="restart"), from_attributes=True)


@router.post("/note-audio-jobs/{job_id}/restart", response_model=NoteAudioExportRead)
def restart_audio_export(job_id: uuid.UUID, user: User = Depends(get_current_user)) -> NoteAudioExportRead:
    job = note_audio_jobs.restart(job_id, user.id)
    if job is None:
        raise NotFoundError("Audioexport nicht gefunden")
    return NoteAudioExportRead.model_validate(job)


def _background_activity(db, user):
    from datetime import datetime, timedelta, timezone
    from app.models.scanner import ScannerScanJob, ScannerDevice
    from app.models.wiki import WikiBackfillRun
    from app.schemas.wiki import WikiBackfillRunRead
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    from app.services.background_activity import activity
    items = activity(user.id, admin=user.is_admin)
    for run in db.scalars(select(WikiBackfillRun).where(
        WikiBackfillRun.owner_id == user.id, WikiBackfillRun.status != "done",
        WikiBackfillRun.updated_at >= cutoff,
    ).order_by(WikiBackfillRun.created_at.desc())):
        items.append(dict(id=str(run.id), kind="wiki", title="Wissensaufbau", status=run.status,
                          progress=WikiBackfillRunRead.model_validate(run).progress,
                          error_message=run.error_message))
    for job, name in db.execute(select(ScannerScanJob, ScannerDevice.name).join(
        ScannerDevice, ScannerDevice.id == ScannerScanJob.scanner_device_id,
    ).where(ScannerScanJob.requested_by_user_id == user.id,
            ScannerScanJob.state.in_(("queued", "scanning", "processing", "error")),
            ScannerScanJob.updated_at >= cutoff)):
        items.append(dict(id=str(job.id), kind="scanner", title=name or "Scanner",
                          status="failed" if job.state == "error" else "queued" if job.state == "queued" else "running",
                          phase=job.state, error_message=job.error))
    return items


@router.post("/jobs/background/{kind}/{job_id}/{action}")
def control_background(kind: str, job_id: uuid.UUID, action: str,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.wiki_backfill import WikiBackfillService
    from app.models.scanner import ScannerScanJob
    from app.services.scanners import ScannerService
    if action not in {"cancel", "restart", "pause", "resume", "dismiss"}:
        raise BadRequestError("Unbekannte Aktion")
    if kind in {"backup", "preanalysis", "cleanup"}:
        if action not in {"cancel", "restart", "dismiss"}:
            raise BadRequestError("Aktion nicht verfügbar")
        from app.services.background_activity import control, dismiss
        if action == "dismiss":
            dismiss(job_id, user.id, admin=user.is_admin)
        else:
            control(job_id, action, user.id, admin=user.is_admin)
    elif kind == "wiki":
        WikiBackfillService(db, user.id).control(job_id, action=action)
    elif kind == "scanner":
        job = db.get(ScannerScanJob, job_id)
        if job is None or job.requested_by_user_id != user.id:
            raise NotFoundError("Scan nicht gefunden")
        if action not in {"cancel", "restart"}:
            raise BadRequestError("Aktion für Scanner nicht verfügbar")
        service = ScannerService(db)
        if job.state in {"queued", "scanning", "processing"}:
            service.cancel_active_scan(job.scanner_device_id, requested_by=user.id)
        if action == "restart":
            service.enqueue_scan_command(job.scanner_device_id, "page", requested_by=user.id)
    else:
        raise NotFoundError("Vorgang nicht gefunden")
    return {"ok": True}
