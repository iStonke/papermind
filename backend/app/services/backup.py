"""Backup auf ein SMB-Netzlaufwerk (NAS).

Sichert die Datenbank (pg_dump) und den PDF-Speicher als Archiv in einen
zeitgestempelten Ordner auf einer SMB-Freigabe, hält die letzten N Backups vor
und protokolliert jeden Lauf in ``backup_runs``.

Die reine Zeitplan-/Aufbewahrungslogik ist als Modulfunktionen ausgelagert und
ohne NAS/DB testbar.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg
from psycopg import sql
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.backup_run import BackupRun
from app.models.job import Job
from app.services.backup_crypto import (
    backup_encryption_key,
    canonical_json_bytes,
    decrypt_file,
    decrypt_secret,
    encrypt_file,
    encrypt_secret,
    manifest_hmac,
    sha256_file,
)
from app.services.maintenance import is_maintenance_active, maintenance_mode, system_state_dir

logger = logging.getLogger("papermind.backup")
settings = get_settings()

_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_BACKUP_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
_DEFAULT_TIME = "03:00"
_RESTORE_STATUS_PATH = system_state_dir() / "restore_status.json"
_RESTORE_DRILL_STATUS_PATH = system_state_dir() / "restore_drill_status.json"
# Ein Lauf, der länger als dies "running" ist, gilt als abgebrochen (Absturz/Neustart).
_STALE_RUN_MINUTES = 120
_BACKUP_FORMAT_VERSION = 2
_OPERATION_LOCK_ID = 0x504D424B  # "PMBK"
_SNAPSHOT_DIR_NAME = ".papermind-backup-snapshots"
_RESERVED_STORAGE_NAMES = {
    ".papermind-system",
    _SNAPSHOT_DIR_NAME,
}


# ── Reine, testbare Helfer ────────────────────────────────────────────────────

def _parse_hhmm(value: str | None) -> tuple[int, int]:
    match = _HHMM_RE.match(str(value or "").strip())
    if not match:
        return (3, 0)
    return (int(match.group(1)), int(match.group(2)))


def previous_scheduled_slot(config: dict, *, now: datetime) -> datetime:
    """Letzter geplanter Zeitpunkt am/vor ``now`` (gleiche tz wie ``now``)."""
    hour, minute = _parse_hhmm(config.get("time", _DEFAULT_TIME))
    today_slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if str(config.get("frequency", "daily")) == "weekly":
        target_wd = int(config.get("weekday", 6)) % 7
        days_back = (now.weekday() - target_wd) % 7
        slot = (now - timedelta(days=days_back)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot > now:
            slot -= timedelta(days=7)
        return slot
    return today_slot if today_slot <= now else today_slot - timedelta(days=1)


def next_scheduled_slot(config: dict, *, now: datetime) -> datetime:
    """Nächster geplanter Zeitpunkt nach ``now``."""
    step = timedelta(days=7) if str(config.get("frequency", "daily")) == "weekly" else timedelta(days=1)
    return previous_scheduled_slot(config, now=now) + step


def is_backup_due(config: dict, *, now: datetime, last_run_at: datetime | None) -> bool:
    """Soll der geplante Backup-Lauf jetzt starten?"""
    if not config.get("enabled"):
        return False
    slot = previous_scheduled_slot(config, now=now)
    return last_run_at is None or last_run_at < slot


def select_old_backup_dirs(dir_names: list[str], retention: int) -> list[str]:
    """Aus zeitgestempelten Ordnernamen die zu löschenden (über ``retention``) wählen."""
    keep = max(1, int(retention or 1))
    valid = sorted((name for name in dir_names if _BACKUP_DIR_RE.match(name)), reverse=True)
    return valid[keep:]


def select_gfs_backup_dirs(
    dir_names: list[str],
    *,
    daily: int,
    weekly: int,
    monthly: int,
) -> list[str]:
    """Wählt zu löschende Archive nach täglicher/wöchentlicher/monatlicher Generation."""
    parsed: list[tuple[str, datetime]] = []
    for name in dir_names:
        if not _BACKUP_DIR_RE.match(name):
            continue
        try:
            parsed.append((name, datetime.strptime(name, "%Y-%m-%d_%H%M%S")))
        except ValueError:
            continue
    parsed.sort(key=lambda item: item[1], reverse=True)
    if not parsed:
        return []

    keep: set[str] = {parsed[0][0]}
    buckets = (
        (max(1, int(daily or 1)), lambda dt: dt.date().isoformat()),
        (max(0, int(weekly or 0)), lambda dt: f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"),
        (max(0, int(monthly or 0)), lambda dt: f"{dt.year:04d}-{dt.month:02d}"),
    )
    for limit, bucket_key in buckets:
        seen: set[str] = set()
        for name, created_at in parsed:
            key = bucket_key(created_at)
            if key in seen:
                continue
            seen.add(key)
            if len(seen) <= limit:
                keep.add(name)
    return [name for name, _ in parsed if name not in keep]


def mask_config(config: dict) -> dict:
    """Konfiguration ohne Rohpasswort, dafür mit ``nas_password_set``-Flag."""
    masked = {
        k: v
        for k, v in config.items()
        if k not in {"nas_password", "secondary_nas_password"}
    }
    masked["nas_password_set"] = bool(str(config.get("nas_password") or "").strip())
    masked["secondary_nas_password_set"] = bool(str(config.get("secondary_nas_password") or "").strip())
    masked["encryption_configured"] = backup_encryption_key() is not None
    return masked


def run_backup_in_background(*, kind: str = "manual") -> None:
    """Backup mit eigener DB-Session ausführen (für Threads/Scheduler)."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        BackupService(db).run_backup(kind=kind)
    finally:
        db.close()


# ── Restore-Status (übersteht den Prozess-Neustart nach dem Restore) ──────────

def write_restore_status(data: dict) -> None:
    try:
        _RESTORE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = _RESTORE_STATUS_PATH.with_name(f"{_RESTORE_STATUS_PATH.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(_RESTORE_STATUS_PATH)
    except Exception:  # noqa: BLE001 - Status ist best effort
        logger.warning("restore status konnte nicht geschrieben werden", exc_info=True)


def read_restore_status() -> dict | None:
    try:
        return json.loads(_RESTORE_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - kein Status vorhanden
        return None


def write_restore_drill_status(data: dict) -> None:
    try:
        _RESTORE_DRILL_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = _RESTORE_DRILL_STATUS_PATH.with_name(
            f"{_RESTORE_DRILL_STATUS_PATH.name}.{uuid.uuid4().hex}.tmp"
        )
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(_RESTORE_DRILL_STATUS_PATH)
    except Exception:  # noqa: BLE001
        logger.warning("restore drill status konnte nicht geschrieben werden", exc_info=True)


def read_restore_drill_status() -> dict | None:
    try:
        return json.loads(_RESTORE_DRILL_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _schedule_process_exit(delay: float = 1.5) -> None:
    """Prozess nach kurzer Verzögerung beenden → Container-Restart-Policy startet sauber neu."""

    def _bye() -> None:
        time.sleep(delay)
        logger.info("restore abgeschlossen – Prozess wird für sauberen Neustart beendet")
        os._exit(0)

    threading.Thread(target=_bye, daemon=True).start()


def run_restore_in_background(*, name: str) -> None:
    """Restore mit eigener DB-Session ausführen (für Threads)."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        BackupService(db).restore_archive(name)
    except Exception:  # noqa: BLE001 - Fehler ist im Status-File protokolliert
        logger.warning("restore im hintergrund fehlgeschlagen name=%s", name, exc_info=True)
    finally:
        db.close()


# ── SMB-Hilfen ────────────────────────────────────────────────────────────────

def _unc(host: str, share: str, *parts: str) -> str:
    tail = "".join(f"\\{p}" for p in parts if p)
    return f"\\\\{host}\\{share}{tail}"


@dataclass
class _SmbTarget:
    host: str
    share: str
    folder: str
    username: str
    password: str

    @classmethod
    def from_config(cls, config: dict, prefix: str = "") -> "_SmbTarget":
        return cls(
            host=str(config.get(f"{prefix}nas_host") or "").strip(),
            share=str(config.get(f"{prefix}nas_share") or "").strip().strip("\\/"),
            folder=str(config.get(f"{prefix}nas_folder") or "").strip().strip("\\/"),
            username=str(config.get(f"{prefix}nas_username") or "").strip(),
            password=str(config.get(f"{prefix}nas_password") or ""),
        )

    def validate(self) -> None:
        if not self.host:
            raise ValueError("NAS-Adresse fehlt")
        if not self.share:
            raise ValueError("Freigabename fehlt")


# smbclient verwaltet seine Sessions in einem globalen, prozessweiten Cache. Laufen
# zwei SMB-Vorgänge gleichzeitig (z. B. eine UI-Abfrage während eines laufenden
# Uploads), entzieht der ``reset_connection_cache()``-Aufruf des einen dem anderen
# die Session – der Upload bleibt dann ohne Timeout endlos hängen. Darum serialisieren
# wir alle SMB-Vorgänge über eine Sperre und geben der Verbindung einen Timeout, damit
# eine nicht reagierende NAS schnell fehlschlägt statt zu blockieren.
_SMB_LOCK = threading.Lock()
_SMB_CONNECTION_TIMEOUT = 30


@contextlib.contextmanager
def _smb_session(target: "_SmbTarget"):
    """Serialisierter SMB-Zugriff mit Timeout; räumt den globalen Cache sauber auf."""
    import smbclient

    with _SMB_LOCK:
        smbclient.reset_connection_cache()
        smbclient.register_session(
            target.host,
            username=target.username,
            password=target.password,
            port=445,
            connection_timeout=_SMB_CONNECTION_TIMEOUT,
        )
        try:
            yield smbclient
        finally:
            try:
                smbclient.reset_connection_cache()
            except Exception:  # noqa: BLE001 - Aufräumen ist best effort
                pass


class BackupService:
    def __init__(self, db: Session):
        self.db = db

    # ── Konfiguration ────────────────────────────────────────────────────────
    def get_config(self) -> dict:
        from app.services.settings import _merge_defaults

        row = self._settings_row()
        merged = _merge_defaults(row.settings_json if row else None)
        config = dict(merged.get("backup") or {})
        key = backup_encryption_key()
        migrated = False
        for field in ("nas_password", "secondary_nas_password"):
            stored = str(config.get(field) or "")
            if stored.startswith("enc:v1:"):
                if key is None:
                    raise RuntimeError(
                        "Backup-Zugangsdaten sind verschlüsselt, aber BACKUP_ENCRYPTION_KEY fehlt"
                    )
                config[field] = decrypt_secret(stored, key)
            elif stored and key is not None and row is not None:
                backup_json = dict((row.settings_json or {}).get("backup") or {})
                backup_json[field] = encrypt_secret(stored, key)
                new_json = dict(row.settings_json or {})
                new_json["backup"] = backup_json
                row.settings_json = new_json
                migrated = True
        if migrated:
            self.db.commit()

        env_overrides = {
            "nas_password": "BACKUP_NAS_PASSWORD",
            "secondary_nas_host": "BACKUP_SECONDARY_NAS_HOST",
            "secondary_nas_share": "BACKUP_SECONDARY_NAS_SHARE",
            "secondary_nas_folder": "BACKUP_SECONDARY_NAS_FOLDER",
            "secondary_nas_username": "BACKUP_SECONDARY_NAS_USERNAME",
            "secondary_nas_password": "BACKUP_SECONDARY_NAS_PASSWORD",
        }
        for field, env_name in env_overrides.items():
            value = str(os.environ.get(env_name) or "").strip()
            if value:
                config[field] = value
        if config.get("secondary_nas_host") and config.get("secondary_nas_share"):
            config["secondary_enabled"] = True
        return config

    def update_config(self, patch: dict) -> dict:
        from app.models.global_setting import GlobalSetting
        from app.services.settings import _merge_defaults

        row = self.db.execute(select(GlobalSetting).where(GlobalSetting.id == 1)).scalar_one_or_none()
        merged = _merge_defaults(row.settings_json if row else None)
        current = dict(merged.get("backup") or {})

        encryption_key = backup_encryption_key()
        for field, value in (patch or {}).items():
            if field in {"nas_password", "secondary_nas_password"}:
                # Passwort nur überschreiben, wenn ein nicht-leerer Wert kommt.
                if str(value or "").strip():
                    if encryption_key is None:
                        raise ValueError(
                            "Zum Speichern von NAS-Passwörtern muss BACKUP_ENCRYPTION_KEY gesetzt sein."
                        )
                    current[field] = encrypt_secret(str(value), encryption_key)
                continue
            if value is not None:
                current[field] = value

        new_json = dict(row.settings_json) if row and isinstance(row.settings_json, dict) else {}
        new_json["backup"] = current
        if row is None:
            row = GlobalSetting(id=1, settings_json=new_json)
            self.db.add(row)
        else:
            row.settings_json = new_json
        self.db.commit()
        return mask_config(self.get_config())

    def _settings_row(self):
        from app.models.global_setting import GlobalSetting

        return self.db.execute(select(GlobalSetting).where(GlobalSetting.id == 1)).scalar_one_or_none()

    @contextlib.contextmanager
    def _exclusive_operation(self):
        acquired = bool(
            self.db.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": _OPERATION_LOCK_ID},
            ).scalar()
        )
        if not acquired:
            raise RuntimeError("Ein Backup oder eine Wiederherstellung läuft bereits.")
        try:
            yield
        finally:
            try:
                self.db.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": _OPERATION_LOCK_ID},
                )
                self.db.commit()
            except Exception:  # noqa: BLE001 - Verbindung kann nach Restore beendet sein
                try:
                    self.db.rollback()
                except Exception:
                    pass

    def _wait_for_running_jobs(self) -> None:
        timeout_seconds = max(5, int(os.environ.get("BACKUP_QUIESCE_TIMEOUT_SECONDS") or 900))
        deadline = time.monotonic() + timeout_seconds
        while True:
            self.db.expire_all()
            running = self.db.execute(
                select(Job.id).where(Job.status == "running").limit(1)
            ).scalar_one_or_none()
            if running is None:
                return
            if time.monotonic() >= deadline:
                raise RuntimeError("Laufende Dokumentverarbeitung konnte nicht rechtzeitig pausiert werden.")
            time.sleep(1)

    @staticmethod
    def _targets(config: dict) -> list[tuple[str, _SmbTarget]]:
        targets = [("primary", _SmbTarget.from_config(config))]
        if config.get("secondary_enabled"):
            targets.append(("secondary", _SmbTarget.from_config(config, "secondary_")))
        for _, target in targets:
            target.validate()
        return targets

    @staticmethod
    def _storage_size_bytes() -> int:
        total = 0
        storage_root = Path(settings.storage_path)
        if not storage_root.is_dir():
            return 0
        for root, directories, files in os.walk(storage_root):
            if Path(root) == storage_root:
                directories[:] = [
                    name
                    for name in directories
                    if name not in _RESERVED_STORAGE_NAMES and not name.startswith(".papermind-restore-")
                ]
            for filename in files:
                try:
                    total += (Path(root) / filename).stat().st_size
                except FileNotFoundError:
                    continue
        return total

    @staticmethod
    def _require_free_space(path: Path, required_bytes: int, operation: str) -> None:
        free = shutil.disk_usage(path).free
        if free < required_bytes:
            required_gib = required_bytes / (1024 ** 3)
            free_gib = free / (1024 ** 3)
            raise RuntimeError(
                f"Zu wenig freier Speicher für {operation}: benötigt ca. {required_gib:.1f} GiB, frei {free_gib:.1f} GiB."
            )

    @staticmethod
    def _send_alert(event: str, message: str) -> None:
        url = str(os.environ.get("BACKUP_ALERT_WEBHOOK_URL") or "").strip()
        if not url:
            return
        try:
            httpx.post(
                url,
                json={
                    "application": "PaperMind",
                    "event": event,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                timeout=10,
            ).raise_for_status()
        except Exception:  # noqa: BLE001 - Alarmierung darf Fehlerpfad nicht verdecken
            logger.warning("backup alert webhook failed", exc_info=True)

    # ── Status ───────────────────────────────────────────────────────────────
    def reap_stale_runs(self) -> int:
        """Läufe, die zu lange ``running`` sind (z.B. durch Absturz/Neustart), als
        fehlgeschlagen markieren – sonst blockieren sie Backups und Restore dauerhaft."""
        threshold = datetime.now().astimezone() - timedelta(minutes=_STALE_RUN_MINUTES)
        stale = (
            self.db.execute(select(BackupRun).where(BackupRun.status == "running", BackupRun.started_at < threshold))
            .scalars()
            .all()
        )
        if not stale:
            return 0
        for run in stale:
            run.status = "failed"
            run.finished_at = datetime.now().astimezone()
            run.error = (run.error + " " if run.error else "") + "Lauf wurde unterbrochen (Timeout)."
        self.db.commit()
        logger.warning("backup: %d hängende Läufe aufgeräumt", len(stale))
        return len(stale)

    def get_status(self) -> dict:
        self.reap_stale_runs()
        config = self.get_config()
        last = self.db.execute(select(BackupRun).order_by(BackupRun.started_at.desc()).limit(1)).scalar_one_or_none()
        last_success = self.db.execute(
            select(BackupRun).where(BackupRun.status == "success").order_by(BackupRun.started_at.desc()).limit(1)
        ).scalar_one_or_none()
        now = datetime.now().astimezone()
        next_run = next_scheduled_slot(config, now=now) if config.get("enabled") else None
        return {
            "config": mask_config(config),
            "last_run": self._run_to_dict(last),
            "last_success_at": last_success.finished_at if last_success else None,
            "next_run_at": next_run,
            "is_running": bool(last and last.status == "running"),
            "last_restore_test_at": (read_restore_drill_status() or {}).get("verified_at"),
        }

    def maybe_alert_stale(self) -> bool:
        config = self.get_config()
        if not config.get("enabled"):
            return False
        last_success = self.db.execute(
            select(BackupRun).where(BackupRun.status == "success").order_by(BackupRun.started_at.desc()).limit(1)
        ).scalar_one_or_none()
        max_age_hours = max(1, int(os.environ.get("BACKUP_ALERT_MAX_AGE_HOURS") or 36))
        now = datetime.now(timezone.utc)
        last_at = last_success.finished_at if last_success else None
        if last_at is not None and last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        if last_at is not None and now - last_at <= timedelta(hours=max_age_hours):
            return False

        state_path = system_state_dir() / "backup_alert_state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            previous = datetime.fromisoformat(str(state.get("stale_alert_at") or ""))
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if now - previous < timedelta(hours=12):
                return False
        except Exception:
            pass
        message = f"Seit mehr als {max_age_hours} Stunden existiert kein erfolgreiches PaperMind-Backup."
        self._send_alert("backup_stale", message)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"stale_alert_at": now.isoformat()}), encoding="utf-8")
        return True

    @staticmethod
    def _run_to_dict(run: BackupRun | None) -> dict | None:
        if run is None:
            return None
        return {
            "id": str(run.id),
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "status": run.status,
            "kind": run.kind,
            "size_bytes": run.size_bytes,
            "location": run.location,
            "error": run.error,
        }

    # ── Verbindungstest ──────────────────────────────────────────────────────
    def test_connection(self) -> dict:
        try:
            targets = self._targets(self.get_config())
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        try:
            for label, target in targets:
                with _smb_session(target) as smbclient:
                    base = _unc(target.host, target.share, target.folder) if target.folder else _unc(target.host, target.share)
                    smbclient.makedirs(base, exist_ok=True)
                    probe = f"{base}\\.papermind_write_test_{label}"
                    with smbclient.open_file(probe, mode="wb") as handle:
                        handle.write(b"ok")
                    smbclient.remove(probe)
            label = "Primär- und Zweitziel" if len(targets) > 1 else "Verbindung"
            return {"ok": True, "message": f"{label} und Schreibzugriff erfolgreich."}
        except Exception as exc:  # noqa: BLE001 - Fehler dem Nutzer melden
            logger.warning("backup test connection failed: %s", exc)
            return {"ok": False, "message": f"Verbindung fehlgeschlagen: {exc}"}

    # ── Backup ausführen ─────────────────────────────────────────────────────
    def run_backup(
        self,
        *,
        kind: str = "manual",
        apply_retention: bool = True,
        preserve_to: Path | None = None,
    ) -> BackupRun:
        run: BackupRun | None = None
        tmp_dir = Path(tempfile.mkdtemp(prefix="pm-backup-"))
        try:
            if is_maintenance_active():
                raise RuntimeError("Wartungsmodus aktiv; Backup kann jetzt nicht gestartet werden.")
            with self._exclusive_operation():
                config = self.get_config()
                targets = self._targets(config)
                if (
                    str(os.environ.get("BACKUP_REQUIRE_ENCRYPTION") or "").lower() in {"1", "true", "yes"}
                    and backup_encryption_key() is None
                ):
                    raise RuntimeError("Backup-Verschlüsselung ist vorgeschrieben, aber kein Schlüssel ist konfiguriert.")

                run = BackupRun(status="running", kind=kind if kind in ("scheduled", "manual") else "manual")
                self.db.add(run)
                self.db.commit()
                self.db.refresh(run)

                stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                self._require_free_space(
                    tmp_dir,
                    self._storage_size_bytes() + 512 * 1024 * 1024,
                    "das Backup",
                )
                files, manifest = self._build_artifacts(tmp_dir, stamp)
                locations: list[str] = []
                for label, target in targets:
                    locations.append(f"{label}:{self._upload_atomic(target, stamp, files)}")
                    if apply_retention:
                        self._apply_retention(target, config)

                if preserve_to is not None:
                    preserve_to.mkdir(parents=True, exist_ok=True)
                    for file_path in files:
                        shutil.copy2(file_path, preserve_to / file_path.name)

                total_size = sum(file_path.stat().st_size for file_path in files)
                run.status = "success"
                run.finished_at = datetime.now().astimezone()
                run.size_bytes = int(total_size)
                run.location = " | ".join(locations)
                self.db.commit()
                self.db.refresh(run)
                (system_state_dir() / "backup_alert_state.json").unlink(missing_ok=True)
                logger.info(
                    "backup success run=%s size=%s encrypted=%s location=%s",
                    run.id,
                    total_size,
                    manifest.get("encrypted"),
                    run.location,
                )
                return run
        except Exception as exc:  # noqa: BLE001 - Lauf als fehlgeschlagen protokollieren
            logger.warning("backup failed run=%s: %s", getattr(run, "id", None), exc)
            self._send_alert("backup_failed", str(exc))
            if run is None:
                run = BackupRun(status="failed", kind=kind if kind in ("scheduled", "manual") else "manual")
                self.db.add(run)
            run.status = "failed"
            run.finished_at = datetime.now().astimezone()
            run.error = str(exc)[:2000]
            try:
                self.db.commit()
                self.db.refresh(run)
            except Exception:
                self.db.rollback()
            return run
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── interne Schritte ─────────────────────────────────────────────────────
    @staticmethod
    def _database_url() -> str:
        database_url = settings.database_url
        if not database_url:
            raise RuntimeError("DATABASE_URL ist nicht gesetzt")
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @classmethod
    def _pg_dump(cls, target_path: Path, *, snapshot_id: str | None = None) -> None:
        command = ["pg_dump", "--dbname", cls._database_url(), "--format", "custom"]
        if snapshot_id:
            command.extend(["--snapshot", snapshot_id])
        command.extend(["--file", str(target_path)])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump fehlgeschlagen: {result.stderr.strip()[:500]}")

    @staticmethod
    def _archive_storage(target_path: Path, snapshot_root: Path) -> None:
        with tarfile.open(target_path, "w:gz") as tar:
            tar.add(snapshot_root, arcname="storage")

    @staticmethod
    def _copy_storage_snapshot(destination: Path) -> None:
        storage_root = Path(settings.storage_path)
        destination.mkdir(parents=True, exist_ok=True)

        def copy_dir(source: Path, target: Path, *, root_level: bool = False) -> None:
            target.mkdir(parents=True, exist_ok=True)
            try:
                entries = list(os.scandir(source))
            except FileNotFoundError:
                return
            for entry in entries:
                if root_level and (
                    entry.name in _RESERVED_STORAGE_NAMES
                    or entry.name.startswith(".papermind-restore-")
                ):
                    continue
                source_path = Path(entry.path)
                target_path = target / entry.name
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        copy_dir(source_path, target_path)
                    elif entry.is_file(follow_symlinks=False) and not target_path.exists():
                        try:
                            os.link(source_path, target_path)
                        except OSError:
                            shutil.copy2(source_path, target_path)
                except FileNotFoundError:
                    continue

        if storage_root.is_dir():
            copy_dir(storage_root, destination, root_level=True)

    @staticmethod
    def _snapshot_storage_keys(connection) -> list[str]:
        document_files_exists = connection.execute(
            "SELECT to_regclass('public.document_files')"
        ).fetchone()[0]
        if document_files_exists:
            query = (
                "SELECT storage_key FROM documents WHERE storage_key IS NOT NULL "
                "UNION SELECT file_key FROM document_files WHERE file_key IS NOT NULL ORDER BY 1"
            )
        else:
            query = "SELECT storage_key FROM documents WHERE storage_key IS NOT NULL ORDER BY 1"
        return [str(row[0]) for row in connection.execute(query).fetchall()]

    @staticmethod
    def _snapshot_database_metadata(connection) -> dict:
        counts: dict[str, int] = {}
        for table_name in (
            "documents",
            "document_files",
            "tags",
            "document_tags",
            "correspondents",
            "correspondent_aliases",
            "correspondent_matchers",
            "document_types",
            "document_retention",
            "users",
        ):
            exists = connection.execute("SELECT to_regclass(%s)", (f"public.{table_name}",)).fetchone()[0]
            if exists:
                counts[table_name] = int(
                    connection.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table_name))).fetchone()[0]
                )

        revision_row = connection.execute(
            "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"
        ).fetchone()
        storage_keys = BackupService._snapshot_storage_keys(connection)
        fingerprint = hashlib.sha256()
        fingerprint_queries = {
            "documents": (
                "SELECT id::text, COALESCE(display_name, ''), COALESCE(document_date::text, ''), "
                "COALESCE(document_type, ''), COALESCE(correspondent_id::text, ''), COALESCE(notes, ''), "
                "COALESCE(is_favorite::text, ''), COALESCE(is_deleted::text, '') FROM documents ORDER BY id"
            ),
            "tags": "SELECT id::text, owner_id::text, name FROM tags ORDER BY id",
            "document_tags": "SELECT document_id::text, tag_id::text FROM document_tags ORDER BY document_id, tag_id",
            "correspondents": (
                "SELECT id::text, owner_id::text, name, COALESCE(short_name, ''), COALESCE(notes, ''), "
                "COALESCE(kind, ''), COALESCE(parent_id::text, '') FROM correspondents ORDER BY id"
            ),
            "correspondent_aliases": (
                "SELECT id::text, correspondent_id::text, alias FROM correspondent_aliases ORDER BY id"
            ),
            "correspondent_matchers": (
                "SELECT id::text, correspondent_id::text, kind, pattern, scope, priority::text "
                "FROM correspondent_matchers ORDER BY id"
            ),
            "document_retention": (
                "SELECT document_id::text, status, COALESCE(period_years::text, ''), "
                "COALESCE(retain_until::text, ''), paper_original, COALESCE(reason, '') "
                "FROM document_retention ORDER BY document_id"
            ),
        }
        for table_name, query in fingerprint_queries.items():
            if table_name not in counts:
                continue
            fingerprint.update(table_name.encode("utf-8"))
            cursor = connection.execute(query)
            while True:
                rows = cursor.fetchmany(500)
                if not rows:
                    break
                for row in rows:
                    fingerprint.update(canonical_json_bytes({"row": list(row)}))

        keys_digest = hashlib.sha256("\n".join(storage_keys).encode("utf-8")).hexdigest()
        return {
            "alembic_revision": revision_row[0] if revision_row else None,
            "counts": counts,
            "document_metadata_sha256": fingerprint.hexdigest(),
            "storage_keys_sha256": keys_digest,
            "storage_keys": storage_keys,
        }

    @staticmethod
    def _verify_snapshot_storage(snapshot_root: Path, storage_keys: list[str]) -> None:
        missing: list[str] = []
        for key in storage_keys:
            relative = Path(str(key))
            if relative.is_absolute() or ".." in relative.parts or not (snapshot_root / relative).is_file():
                missing.append(str(key))
                if len(missing) >= 10:
                    break
        if missing:
            raise RuntimeError(f"Snapshot enthält nicht alle referenzierten Dokumentdateien: {missing}")

    def _build_artifacts(self, tmp_dir: Path, stamp: str) -> tuple[list[Path], dict]:
        storage_root = Path(settings.storage_path)
        snapshot_base = storage_root / _SNAPSHOT_DIR_NAME
        snapshot_root = snapshot_base / uuid.uuid4().hex
        db_dump = tmp_dir / "database.dump"
        storage_archive = tmp_dir / "storage.tar.gz"
        metadata: dict = {}
        try:
            with maintenance_mode("backup_snapshot"):
                self._wait_for_running_jobs()
                self._copy_storage_snapshot(snapshot_root)
                with psycopg.connect(self._database_url()) as connection:
                    connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    snapshot_id = connection.execute("SELECT pg_export_snapshot()").fetchone()[0]
                    self._pg_dump(db_dump, snapshot_id=str(snapshot_id))
                    metadata = self._snapshot_database_metadata(connection)
                    # Zweiter Durchlauf ergänzt Dateien, die unmittelbar vor dem
                    # DB-Snapshot angelegt wurden. Bereits verlinkte Dateien bleiben
                    # auf dem Stand vor dem Snapshot erhalten.
                    self._copy_storage_snapshot(snapshot_root)
                    self._verify_snapshot_storage(snapshot_root, metadata["storage_keys"])
                    connection.commit()

            self._archive_storage(storage_archive, snapshot_root)
        finally:
            shutil.rmtree(snapshot_root, ignore_errors=True)
            try:
                snapshot_base.rmdir()
            except OSError:
                pass

        plain_artifacts = [db_dump, storage_archive]
        key = backup_encryption_key()
        manifest_artifacts: list[dict] = []
        stored_artifacts: list[Path] = []
        for artifact in plain_artifacts:
            plain_sha = sha256_file(artifact)
            plain_size = artifact.stat().st_size
            stored = artifact
            if key is not None:
                stored = artifact.with_name(f"{artifact.name}.enc")
                encrypt_file(artifact, stored, key)
                artifact.unlink()
            stored_artifacts.append(stored)
            manifest_artifacts.append(
                {
                    "logical_name": artifact.name,
                    "filename": stored.name,
                    "size_bytes": stored.stat().st_size,
                    "sha256": sha256_file(stored),
                    "plaintext_size_bytes": plain_size,
                    "plaintext_sha256": plain_sha,
                }
            )

        manifest = {
            "format_version": _BACKUP_FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stamp": stamp,
            "app_version": settings.app_version,
            "app_revision": str(os.environ.get("APP_REVISION") or "unknown"),
            "encrypted": key is not None,
            "encryption": "AES-256-GCM" if key is not None else None,
            "database": {
                "alembic_revision": metadata.get("alembic_revision"),
                "counts": metadata.get("counts", {}),
                "document_metadata_sha256": metadata.get("document_metadata_sha256"),
                "storage_keys_sha256": metadata.get("storage_keys_sha256"),
                "storage_key_count": len(metadata.get("storage_keys", [])),
            },
            "artifacts": manifest_artifacts,
        }
        if key is not None:
            manifest["hmac_sha256"] = manifest_hmac(manifest, key)
        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        return [*stored_artifacts, manifest_path], manifest

    @staticmethod
    def _remote_sha256(smbclient, path: str) -> str:
        digest = hashlib.sha256()
        with smbclient.open_file(path, mode="rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _upload_atomic(target: _SmbTarget, stamp: str, files: list[Path]) -> str:
        with _smb_session(target) as smbclient:
            root = BackupService._archive_root(target)
            smbclient.makedirs(root, exist_ok=True)
            temporary = f"{root}\\.incomplete-{stamp}-{uuid.uuid4().hex[:8]}"
            destination = f"{root}\\{stamp}"
            smbclient.makedirs(temporary, exist_ok=False)
            try:
                for file_path in files:
                    remote = f"{temporary}\\{file_path.name}"
                    with open(file_path, "rb") as src, smbclient.open_file(remote, mode="wb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                    remote_stat = smbclient.stat(remote)
                    if int(remote_stat.st_size) != file_path.stat().st_size:
                        raise RuntimeError(f"Uploadgröße stimmt nicht: {file_path.name}")
                    if BackupService._remote_sha256(smbclient, remote) != sha256_file(file_path):
                        raise RuntimeError(f"Upload-Prüfsumme stimmt nicht: {file_path.name}")
                smbclient.rename(temporary, destination)
                return destination
            except Exception:
                try:
                    BackupService._smb_rmtree(smbclient, temporary)
                except Exception:
                    logger.warning("unvollständiger Backup-Ordner konnte nicht entfernt werden: %s", temporary)
                raise

    @staticmethod
    def _apply_retention(target: _SmbTarget, config: dict) -> None:
        with _smb_session(target) as smbclient:
            root = _unc(target.host, target.share, target.folder) if target.folder else _unc(target.host, target.share)
            names = []
            for entry in smbclient.scandir(root):
                if entry.is_dir():
                    if entry.name.startswith(".incomplete-"):
                        try:
                            if time.time() - float(entry.stat().st_mtime) > 24 * 3600:
                                BackupService._smb_rmtree(smbclient, f"{root}\\{entry.name}")
                        except Exception:
                            logger.warning("stale incomplete backup could not be removed: %s", entry.name)
                        continue
                    names.append(entry.name)
            daily = int(config.get("retention_daily") or config.get("retention") or 7)
            weekly = int(config.get("retention_weekly") or 0)
            monthly = int(config.get("retention_monthly") or 0)
            for name in select_gfs_backup_dirs(names, daily=daily, weekly=weekly, monthly=monthly):
                BackupService._smb_rmtree(smbclient, f"{root}\\{name}")

    @staticmethod
    def _smb_rmtree(smbclient, path: str) -> None:
        for entry in smbclient.scandir(path):
            child = f"{path}\\{entry.name}"
            if entry.is_dir():
                BackupService._smb_rmtree(smbclient, child)
            else:
                smbclient.remove(child)
        smbclient.rmdir(path)

    # ── Archive (vorhandene Backups verwalten) ───────────────────────────────
    @staticmethod
    def _archive_created_at(name: str) -> datetime | None:
        try:
            return datetime.strptime(name, "%Y-%m-%d_%H%M%S").astimezone()
        except ValueError:
            return None

    def list_archives(self) -> list[dict]:
        """Vorhandene Backup-Ordner auf dem NAS samt Gesamtgröße auflisten."""
        errors: list[str] = []
        for label, target in self._targets(self.get_config()):
            try:
                return self._list_archives_from_target(target)
            except Exception as exc:  # noqa: BLE001 - Zweitziel als Fallback
                errors.append(f"{label}: {exc}")
        raise RuntimeError("Kein Backup-Ziel erreichbar: " + " | ".join(errors))

    def _list_archives_from_target(self, target: _SmbTarget) -> list[dict]:
        with _smb_session(target) as smbclient:
            root = self._archive_root(target)
            items: list[dict] = []
            for entry in smbclient.scandir(root):
                if not (entry.is_dir() and _BACKUP_DIR_RE.match(entry.name)):
                    continue
                size = 0
                names: set[str] = set()
                sizes: dict[str, int] = {}
                manifest: dict | None = None
                try:
                    for f in smbclient.scandir(f"{root}\\{entry.name}"):
                        if not f.is_dir():
                            file_size = int(f.stat().st_size)
                            size += file_size
                            names.add(f.name)
                            sizes[f.name] = file_size
                    if "manifest.json" in names:
                        with smbclient.open_file(f"{root}\\{entry.name}\\manifest.json", mode="rb") as handle:
                            manifest = json.loads(handle.read().decode("utf-8"))
                except Exception:  # noqa: BLE001 - unvollständiger Ordner
                    pass
                if manifest:
                    artifacts = manifest.get("artifacts") or []
                    complete = all(
                        str(item.get("filename") or "") in names
                        and sizes.get(str(item.get("filename") or "")) == int(item.get("size_bytes") or -1)
                        for item in artifacts
                    ) and len(artifacts) >= 2
                    verified = False
                    key = backup_encryption_key()
                    expected_hmac = str(manifest.get("hmac_sha256") or "")
                    if expected_hmac and key is not None:
                        unsigned = dict(manifest)
                        unsigned.pop("hmac_sha256", None)
                        verified = hmac.compare_digest(expected_hmac, manifest_hmac(unsigned, key))
                        complete = complete and verified
                else:
                    complete = {"database.dump", "storage.tar.gz"}.issubset(names)
                    verified = False
                items.append(
                    {
                        "name": entry.name,
                        "size_bytes": int(size),
                        "created_at": self._archive_created_at(entry.name),
                        "complete": complete,
                        "verified": verified,
                        "encrypted": bool(manifest and manifest.get("encrypted")),
                        "format_version": manifest.get("format_version") if manifest else 1,
                    }
                )
            items.sort(key=lambda x: x["name"], reverse=True)
            return items

    def delete_archive(self, name: str) -> None:
        if not _BACKUP_DIR_RE.match(name):
            raise ValueError("Ungültiger Backup-Name")
        targets = self._targets(self.get_config())
        errors: list[str] = []
        deleted = False
        for label, target in targets:
            try:
                with _smb_session(target) as smbclient:
                    self._smb_rmtree(smbclient, f"{self._archive_root(target)}\\{name}")
                deleted = True
            except Exception as exc:  # noqa: BLE001 - beide Ziele best effort
                errors.append(f"{label}: {exc}")
        if not deleted:
            raise RuntimeError("Backup konnte auf keinem Ziel gelöscht werden: " + " | ".join(errors))

    @staticmethod
    def _archive_root(target: _SmbTarget) -> str:
        return _unc(target.host, target.share, target.folder) if target.folder else _unc(target.host, target.share)

    # ── Restore ──────────────────────────────────────────────────────────────
    def restore_archive(self, name: str, *, do_exit: bool = True) -> None:
        """Archiv vorprüfen, Sicherheitsbackup anlegen und erst dann einspielen."""
        if not _BACKUP_DIR_RE.match(name):
            raise ValueError("Ungültiger Backup-Name")

        targets = self._targets(self.get_config())
        started = datetime.now().astimezone()
        write_restore_status({"status": "running", "name": name, "started_at": started.isoformat()})

        tmp_dir = Path(tempfile.mkdtemp(prefix="pm-restore-"))
        production_changed = False
        safety_name: str | None = None
        try:
            archive = next((item for item in self.list_archives() if item.get("name") == name), None)
            if archive:
                self._require_free_space(
                    tmp_dir,
                    int(archive.get("size_bytes") or 0) * 3 + 1024 * 1024 * 1024,
                    "die Wiederherstellung",
                )
            download_errors: list[str] = []
            for label, target in targets:
                try:
                    db_dump, storage_archive, manifest = self._download_and_prepare_archive(
                        target,
                        name,
                        tmp_dir / f"source-{label}",
                    )
                    break
                except Exception as download_error:  # noqa: BLE001 - Fallback aufs Zweitziel
                    download_errors.append(f"{label}: {download_error}")
            else:
                raise RuntimeError("Archiv konnte von keinem Ziel geladen werden: " + " | ".join(download_errors))
            self._validate_restore_candidate(db_dump, storage_archive, manifest, tmp_dir / "validation")

            safety_dir = tmp_dir / "safety"
            safety_run = self.run_backup(kind="manual", apply_retention=False, preserve_to=safety_dir)
            if safety_run.status != "success":
                raise RuntimeError(f"Sicherheitsbackup vor Restore fehlgeschlagen: {safety_run.error or 'unbekannt'}")
            safety_manifest = json.loads((safety_dir / "manifest.json").read_text(encoding="utf-8"))
            safety_name = str(safety_manifest.get("stamp") or "") or None
            rollback_db, rollback_storage, _ = self._prepare_local_archive(safety_dir, tmp_dir / "rollback")

            with self._exclusive_operation():
                with maintenance_mode("restore"):
                    self._wait_for_running_jobs()
                    production_changed = True
                    self._pg_restore(db_dump)
                    self._restore_storage(storage_archive)
                    self._finalize_restored_runtime_state()
                    self._validate_live_database(manifest)

            verified_at = datetime.now().astimezone()
            write_restore_status(
                {
                    "status": "success",
                    "name": name,
                    "started_at": started.isoformat(),
                    "finished_at": verified_at.isoformat(),
                    "verified_at": verified_at.isoformat(),
                    "safety_backup": safety_name,
                }
            )
            logger.info("restore success name=%s safety_backup=%s", name, safety_name)
        except Exception as exc:  # noqa: BLE001 - Fehler im Status protokollieren
            if production_changed:
                try:
                    rollback_db = locals().get("rollback_db")
                    rollback_storage = locals().get("rollback_storage")
                    if rollback_db and rollback_storage:
                        with maintenance_mode("restore_rollback"):
                            self._pg_restore(rollback_db)
                            self._restore_storage(rollback_storage)
                        logger.warning("restore rollback completed safety_backup=%s", safety_name)
                except Exception as rollback_exc:  # noqa: BLE001
                    logger.exception("automatic restore rollback failed")
                    exc = RuntimeError(f"{exc}; automatischer Rollback fehlgeschlagen: {rollback_exc}")
            write_restore_status(
                {
                    "status": "failed",
                    "name": name,
                    "error": str(exc)[:2000],
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now().astimezone().isoformat(),
                    "safety_backup": safety_name,
                }
            )
            self._send_alert("restore_failed", str(exc))
            logger.warning("restore failed name=%s: %s", name, exc)
            raise
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        if do_exit:
            _schedule_process_exit()

    @staticmethod
    def _download(target: _SmbTarget, name: str, filename: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with _smb_session(target) as smbclient:
            parts = [p for p in (target.folder, name) if p]
            remote = _unc(target.host, target.share, *parts, filename)
            with smbclient.open_file(remote, mode="rb") as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)

    def _download_and_prepare_archive(
        self,
        target: _SmbTarget,
        name: str,
        destination: Path,
    ) -> tuple[Path, Path, dict | None]:
        destination.mkdir(parents=True, exist_ok=True)
        manifest_path = destination / "manifest.json"
        try:
            self._download(target, name, "manifest.json", manifest_path)
        except Exception:
            manifest = None
            manifest_path.unlink(missing_ok=True)
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise RuntimeError("Backupmanifest ist nicht lesbar.") from exc

        if manifest is None:
            db_dump = destination / "database.dump"
            storage_archive = destination / "storage.tar.gz"
            self._download(target, name, db_dump.name, db_dump)
            self._download(target, name, storage_archive.name, storage_archive)
            return db_dump, storage_archive, None
        return self._download_manifest_artifacts(target, name, destination, manifest)

    def _download_manifest_artifacts(
        self,
        target: _SmbTarget,
        name: str,
        destination: Path,
        manifest: dict,
    ) -> tuple[Path, Path, dict]:
        if int(manifest.get("format_version") or 0) != _BACKUP_FORMAT_VERSION:
            raise RuntimeError("Nicht unterstützte Backupformat-Version")
        key = backup_encryption_key()
        expected_hmac = str(manifest.get("hmac_sha256") or "")
        if manifest.get("encrypted") and not expected_hmac:
            raise RuntimeError("Verschlüsseltes Backup besitzt keine Manifest-Signatur.")
        if expected_hmac:
            if key is None:
                raise RuntimeError("Dieses Backup ist verschlüsselt; BACKUP_ENCRYPTION_KEY fehlt.")
            unsigned = dict(manifest)
            unsigned.pop("hmac_sha256", None)
            if not hmac.compare_digest(expected_hmac, manifest_hmac(unsigned, key)):
                raise RuntimeError("Manifest-Signatur ist ungültig.")

        logical_paths: dict[str, Path] = {}
        for artifact in manifest.get("artifacts") or []:
            filename = str(artifact.get("filename") or "")
            logical_name = str(artifact.get("logical_name") or "")
            if Path(filename).name != filename or logical_name not in {"database.dump", "storage.tar.gz"}:
                raise RuntimeError("Manifest enthält einen ungültigen Artefaktpfad.")
            stored_path = destination / filename
            self._download(target, name, filename, stored_path)
            if stored_path.stat().st_size != int(artifact.get("size_bytes") or -1):
                raise RuntimeError(f"Backupgröße stimmt nicht: {filename}")
            if sha256_file(stored_path) != str(artifact.get("sha256") or ""):
                raise RuntimeError(f"Backup-Prüfsumme stimmt nicht: {filename}")
            logical_path = destination / logical_name
            if manifest.get("encrypted"):
                if key is None:
                    raise RuntimeError("Backup-Schlüssel fehlt.")
                decrypt_file(stored_path, logical_path, key)
            else:
                shutil.copy2(stored_path, logical_path)
            if logical_path.stat().st_size != int(artifact.get("plaintext_size_bytes") or -1):
                raise RuntimeError(f"Entschlüsselte Backupgröße stimmt nicht: {logical_name}")
            if sha256_file(logical_path) != str(artifact.get("plaintext_sha256") or ""):
                raise RuntimeError(f"Entschlüsselte Prüfsumme stimmt nicht: {logical_name}")
            logical_paths[logical_name] = logical_path
        if set(logical_paths) != {"database.dump", "storage.tar.gz"}:
            raise RuntimeError("Backupmanifest ist unvollständig.")
        return logical_paths["database.dump"], logical_paths["storage.tar.gz"], manifest

    def _prepare_local_archive(self, source: Path, destination: Path) -> tuple[Path, Path, dict]:
        destination.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        key = backup_encryption_key()
        logical: dict[str, Path] = {}
        for artifact in manifest.get("artifacts") or []:
            stored = source / str(artifact["filename"])
            target = destination / str(artifact["logical_name"])
            if manifest.get("encrypted"):
                if key is None:
                    raise RuntimeError("Backup-Schlüssel für Sicherheitsbackup fehlt.")
                decrypt_file(stored, target, key)
            else:
                shutil.copy2(stored, target)
            if sha256_file(target) != str(artifact.get("plaintext_sha256") or ""):
                raise RuntimeError("Lokales Sicherheitsbackup ist beschädigt.")
            logical[str(artifact["logical_name"])] = target
        return logical["database.dump"], logical["storage.tar.gz"], manifest

    @staticmethod
    def _terminate_other_connections(database_url: str) -> None:
        try:
            subprocess.run(
                [
                    "psql",
                    database_url,
                    "-v",
                    "ON_ERROR_STOP=0",
                    "-c",
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid();",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:  # noqa: BLE001 - best effort
            logger.warning("Fremdverbindungen konnten nicht getrennt werden", exc_info=True)

    @classmethod
    def _pg_restore_to_url(cls, dump_path: Path, database_url: str, *, clean: bool) -> None:
        command = ["pg_restore", "--exit-on-error", "--dbname", database_url]
        if clean:
            command.extend(["--clean", "--if-exists"])
        command.extend(["--no-owner", "--no-acl", str(dump_path)])
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"Exit {result.returncode}"
            raise RuntimeError(f"pg_restore fehlgeschlagen: {detail[:1000]}")

    @classmethod
    def _pg_restore(cls, dump_path: Path) -> None:
        database_url = cls._database_url()
        cls._terminate_other_connections(database_url)
        reset = subprocess.run(
            [
                "psql",
                database_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "DROP SCHEMA public CASCADE; CREATE SCHEMA public;",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if reset.returncode != 0:
            detail = reset.stderr.strip() or reset.stdout.strip() or f"Exit {reset.returncode}"
            raise RuntimeError(f"Datenbankschema konnte nicht vorbereitet werden: {detail[:1000]}")
        cls._pg_restore_to_url(dump_path, database_url, clean=False)

    @classmethod
    def _create_shadow_database(cls, database_name: str) -> str:
        url = make_url(cls._database_url())
        admin_url = url.set(database="postgres").render_as_string(hide_password=False)
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))
            connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database_name)))
        return url.set(database=database_name).render_as_string(hide_password=False)

    @classmethod
    def _drop_shadow_database(cls, database_name: str) -> None:
        url = make_url(cls._database_url())
        admin_url = url.set(database="postgres").render_as_string(hide_password=False)
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))

    def _validate_restore_candidate(
        self,
        db_dump: Path,
        storage_archive: Path,
        manifest: dict | None,
        validation_root: Path,
    ) -> None:
        result = subprocess.run(
            ["pg_restore", "--list", str(db_dump)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Datenbank-Dump ist nicht lesbar: {result.stderr[:500]}")
        validation_root.mkdir(parents=True, exist_ok=True)
        extracted = validation_root / "storage"
        self._extract_storage_archive(storage_archive, extracted)

        shadow_name = f"papermind_restore_check_{uuid.uuid4().hex[:12]}"
        shadow_url = self._create_shadow_database(shadow_name)
        try:
            self._pg_restore_to_url(db_dump, shadow_url, clean=False)
            with psycopg.connect(shadow_url) as connection:
                if manifest:
                    actual = self._snapshot_database_metadata(connection)
                    self._verify_snapshot_storage(extracted, actual["storage_keys"])
                    expected = manifest.get("database") or {}
                    if actual["counts"] != expected.get("counts", {}):
                        raise RuntimeError("Tabellenzähler stimmen nicht mit dem Backupmanifest überein.")
                    if actual["document_metadata_sha256"] != expected.get("document_metadata_sha256"):
                        raise RuntimeError("Dokumentmetadaten stimmen nicht mit dem Backupmanifest überein.")
                    if actual["storage_keys_sha256"] != expected.get("storage_keys_sha256"):
                        raise RuntimeError("Dateireferenzen stimmen nicht mit dem Backupmanifest überein.")
                else:
                    self._verify_snapshot_storage(extracted, self._snapshot_storage_keys(connection))
        finally:
            self._drop_shadow_database(shadow_name)

    def _validate_live_database(self, manifest: dict | None) -> None:
        if manifest is None:
            return
        with psycopg.connect(self._database_url()) as connection:
            actual = self._snapshot_database_metadata(connection)
        expected = manifest.get("database") or {}
        if actual["document_metadata_sha256"] != expected.get("document_metadata_sha256"):
            raise RuntimeError("Produktive Metadatenprüfung nach Restore fehlgeschlagen.")

    @classmethod
    def _finalize_restored_runtime_state(cls) -> None:
        with psycopg.connect(cls._database_url()) as connection:
            if connection.execute("SELECT to_regclass('public.backup_runs')").fetchone()[0]:
                connection.execute(
                    "UPDATE backup_runs SET status = 'failed', finished_at = now(), "
                    "error = COALESCE(error || ' ', '') || 'Durch Wiederherstellung unterbrochen.' "
                    "WHERE status = 'running'"
                )
            connection.commit()

    @staticmethod
    def _extract_storage_archive(archive_path: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pm-storage-extract-") as temporary:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(temporary, filter="data")
            source = Path(temporary) / "storage"
            if not source.is_dir():
                source = Path(temporary)
            for child in source.iterdir():
                target = destination / child.name
                if child.is_dir():
                    shutil.copytree(child, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, target)

    @staticmethod
    def _restore_storage(archive_path: Path) -> None:
        storage_root = Path(settings.storage_path)
        storage_root.mkdir(parents=True, exist_ok=True)
        stage = storage_root / f".papermind-restore-stage-{uuid.uuid4().hex}"
        rollback = storage_root / f".papermind-restore-rollback-{uuid.uuid4().hex}"
        BackupService._extract_storage_archive(archive_path, stage)
        rollback.mkdir(parents=True, exist_ok=False)
        moved_current: list[tuple[Path, Path]] = []
        moved_stage: list[tuple[Path, Path]] = []
        try:
            for child in list(storage_root.iterdir()):
                if (
                    child in {stage, rollback}
                    or child.name in _RESERVED_STORAGE_NAMES
                    or child.name.startswith(".papermind-restore-")
                ):
                    continue
                destination = rollback / child.name
                child.replace(destination)
                moved_current.append((destination, child))
            for child in list(stage.iterdir()):
                destination = storage_root / child.name
                child.replace(destination)
                moved_stage.append((destination, child))
        except Exception:
            for current, original in reversed(moved_stage):
                if current.exists():
                    current.replace(original)
            for saved, original in reversed(moved_current):
                if saved.exists():
                    saved.replace(original)
            raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(rollback, ignore_errors=True)
