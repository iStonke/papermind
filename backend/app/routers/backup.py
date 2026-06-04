import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.backup import (
    BackupArchiveListResponse,
    BackupConfigPatch,
    BackupRestoreRequest,
    BackupRestoreStatusResponse,
    BackupRunStartResponse,
    BackupStatusResponse,
    BackupTestResponse,
)
from app.schemas.common import OkResponse
from app.services.backup import (
    BackupService,
    read_restore_status,
    run_backup_in_background,
    run_restore_in_background,
)

router = APIRouter(prefix="/api/backup", tags=["Backup"])


@router.get("", response_model=BackupStatusResponse, summary="Backup-Konfiguration und -Status")
def get_backup_status(db: Session = Depends(get_db)) -> BackupStatusResponse:
    return BackupStatusResponse(**BackupService(db).get_status())


@router.patch("", response_model=BackupStatusResponse, summary="Backup-Konfiguration aktualisieren")
def update_backup_config(payload: BackupConfigPatch, db: Session = Depends(get_db)) -> BackupStatusResponse:
    service = BackupService(db)
    service.update_config(payload.model_dump(exclude_unset=True))
    return BackupStatusResponse(**service.get_status())


@router.post("/test", response_model=BackupTestResponse, summary="NAS-Verbindung testen")
def test_backup_connection(db: Session = Depends(get_db)) -> BackupTestResponse:
    return BackupTestResponse(**BackupService(db).test_connection())


@router.post("/run", response_model=BackupRunStartResponse, summary="Backup jetzt starten")
def run_backup_now(db: Session = Depends(get_db)) -> BackupRunStartResponse:
    status = BackupService(db).get_status()
    if status.get("is_running"):
        return BackupRunStartResponse(started=False, message="Ein Backup läuft bereits.")
    threading.Thread(target=run_backup_in_background, kwargs={"kind": "manual"}, daemon=True).start()
    return BackupRunStartResponse(started=True, message="Backup gestartet.")


@router.get("/archives", response_model=BackupArchiveListResponse, summary="Vorhandene Backups auflisten")
def list_backup_archives(db: Session = Depends(get_db)) -> BackupArchiveListResponse:
    try:
        return BackupArchiveListResponse(items=BackupService(db).list_archives())
    except Exception as exc:  # noqa: BLE001 - NAS nicht erreichbar o.ä.
        raise HTTPException(status_code=502, detail=f"Backups konnten nicht gelesen werden: {exc}") from exc


@router.delete("/archives/{name}", response_model=OkResponse, summary="Ein Backup löschen")
def delete_backup_archive(name: str, db: Session = Depends(get_db)) -> OkResponse:
    try:
        BackupService(db).delete_archive(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Backup konnte nicht gelöscht werden: {exc}") from exc
    return OkResponse()


@router.get("/restore-status", response_model=BackupRestoreStatusResponse, summary="Status der letzten Wiederherstellung")
def get_restore_status() -> BackupRestoreStatusResponse:
    return BackupRestoreStatusResponse(**(read_restore_status() or {}))


@router.post("/restore", response_model=BackupRunStartResponse, summary="Backup wiederherstellen")
def restore_backup(payload: BackupRestoreRequest, db: Session = Depends(get_db)) -> BackupRunStartResponse:
    status = BackupService(db).get_status()
    if status.get("is_running"):
        return BackupRunStartResponse(started=False, message="Ein Backup läuft gerade – bitte später erneut versuchen.")
    current = read_restore_status() or {}
    if current.get("status") == "running":
        return BackupRunStartResponse(started=False, message="Eine Wiederherstellung läuft bereits.")
    threading.Thread(target=run_restore_in_background, kwargs={"name": payload.name}, daemon=True).start()
    return BackupRunStartResponse(started=True, message="Wiederherstellung gestartet.")
