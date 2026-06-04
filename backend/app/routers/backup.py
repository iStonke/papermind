import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.backup import (
    BackupConfigPatch,
    BackupRunStartResponse,
    BackupStatusResponse,
    BackupTestResponse,
)
from app.services.backup import BackupService, run_backup_in_background

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
