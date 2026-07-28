"""Gemeinsamer Wartungsmodus für Backend und Worker.

Der Marker liegt auf dem gemeinsam eingebundenen Dokument-Volume. Dadurch sehen
Backend und Worker denselben Zustand, obwohl sie in getrennten Containern laufen.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


_SYSTEM_DIR_NAME = ".papermind-system"
_MAINTENANCE_FILE_NAME = "maintenance.json"


def system_state_dir() -> Path:
    configured = str(os.environ.get("BACKUP_STATE_PATH") or "").strip()
    if configured:
        return Path(configured)
    return Path(get_settings().storage_path) / _SYSTEM_DIR_NAME


def maintenance_marker_path() -> Path:
    return system_state_dir() / _MAINTENANCE_FILE_NAME


def _lease_seconds() -> int:
    return max(30, int(os.environ.get("BACKUP_MAINTENANCE_LEASE_SECONDS") or 90))


def _write_marker(payload: dict) -> None:
    path = maintenance_marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _read_marker() -> dict | None:
    try:
        return json.loads(maintenance_marker_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def is_maintenance_active() -> bool:
    path = maintenance_marker_path()
    if not path.is_file():
        return False
    payload = _read_marker()
    try:
        if payload:
            updated_at = datetime.fromisoformat(str(payload.get("updated_at") or payload.get("started_at")))
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - updated_at).total_seconds()
        else:
            age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    except (OSError, ValueError, TypeError):
        age = 0
    if age <= _lease_seconds():
        return True
    clear_maintenance_marker(str((payload or {}).get("token") or "") or None)
    return False


def write_maintenance_marker(reason: str, *, token: str | None = None) -> str:
    marker_token = token or uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    _write_marker(
        {
            "reason": str(reason or "backup"),
            "started_at": now,
            "updated_at": now,
            "pid": os.getpid(),
            "token": marker_token,
        }
    )
    return marker_token


def clear_maintenance_marker(token: str | None = None) -> None:
    if token:
        payload = _read_marker()
        if payload and str(payload.get("token") or "") != token:
            return
    maintenance_marker_path().unlink(missing_ok=True)


@contextmanager
def maintenance_mode(reason: str):
    token = write_maintenance_marker(reason)
    stopped = threading.Event()

    def heartbeat() -> None:
        while not stopped.wait(10):
            payload = _read_marker()
            if not payload or str(payload.get("token") or "") != token:
                return
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_marker(payload)

    heartbeat_thread = threading.Thread(target=heartbeat, name="backup-maintenance-heartbeat", daemon=True)
    heartbeat_thread.start()
    try:
        yield
    finally:
        stopped.set()
        heartbeat_thread.join(timeout=1)
        clear_maintenance_marker(token)
