"""Backup auf ein SMB-Netzlaufwerk (NAS).

Sichert die Datenbank (pg_dump) und den PDF-Speicher als Archiv in einen
zeitgestempelten Ordner auf einer SMB-Freigabe, hält die letzten N Backups vor
und protokolliert jeden Lauf in ``backup_runs``.

Die reine Zeitplan-/Aufbewahrungslogik ist als Modulfunktionen ausgelagert und
ohne NAS/DB testbar.
"""

from __future__ import annotations

import contextlib
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
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.backup_run import BackupRun

logger = logging.getLogger("papermind.backup")
settings = get_settings()

_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_BACKUP_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
_DEFAULT_TIME = "03:00"
_RESTORE_STATUS_PATH = Path(tempfile.gettempdir()) / "pm_restore_status.json"
# Ein Lauf, der länger als dies "running" ist, gilt als abgebrochen (Absturz/Neustart).
_STALE_RUN_MINUTES = 120


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


def mask_config(config: dict) -> dict:
    """Konfiguration ohne Rohpasswort, dafür mit ``nas_password_set``-Flag."""
    masked = {k: v for k, v in config.items() if k != "nas_password"}
    masked["nas_password_set"] = bool(str(config.get("nas_password") or "").strip())
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
        _RESTORE_STATUS_PATH.write_text(json.dumps(data), encoding="utf-8")
    except Exception:  # noqa: BLE001 - Status ist best effort
        logger.warning("restore status konnte nicht geschrieben werden", exc_info=True)


def read_restore_status() -> dict | None:
    try:
        return json.loads(_RESTORE_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - kein Status vorhanden
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
    def from_config(cls, config: dict) -> "_SmbTarget":
        return cls(
            host=str(config.get("nas_host") or "").strip(),
            share=str(config.get("nas_share") or "").strip().strip("\\/"),
            folder=str(config.get("nas_folder") or "").strip().strip("\\/"),
            username=str(config.get("nas_username") or "").strip(),
            password=str(config.get("nas_password") or ""),
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
        return dict(merged.get("backup") or {})

    def update_config(self, patch: dict) -> dict:
        from app.models.global_setting import GlobalSetting
        from app.services.settings import _merge_defaults

        row = self.db.execute(select(GlobalSetting).where(GlobalSetting.id == 1)).scalar_one_or_none()
        merged = _merge_defaults(row.settings_json if row else None)
        current = dict(merged.get("backup") or {})

        for key, value in (patch or {}).items():
            if key == "nas_password":
                # Passwort nur überschreiben, wenn ein nicht-leerer Wert kommt.
                if str(value or "").strip():
                    current[key] = value
                continue
            if value is not None:
                current[key] = value

        new_json = dict(row.settings_json) if row and isinstance(row.settings_json, dict) else {}
        new_json["backup"] = current
        if row is None:
            row = GlobalSetting(id=1, settings_json=new_json)
            self.db.add(row)
        else:
            row.settings_json = new_json
        self.db.commit()
        return mask_config(current)

    def _settings_row(self):
        from app.models.global_setting import GlobalSetting

        return self.db.execute(select(GlobalSetting).where(GlobalSetting.id == 1)).scalar_one_or_none()

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
        }

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
        target = _SmbTarget.from_config(self.get_config())
        try:
            target.validate()
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        try:
            with _smb_session(target) as smbclient:
                base = _unc(target.host, target.share, target.folder) if target.folder else _unc(target.host, target.share)
                smbclient.makedirs(base, exist_ok=True)
                probe = f"{base}\\.papermind_write_test"
                with smbclient.open_file(probe, mode="wb") as handle:
                    handle.write(b"ok")
                smbclient.remove(probe)
            return {"ok": True, "message": "Verbindung und Schreibzugriff erfolgreich."}
        except Exception as exc:  # noqa: BLE001 - Fehler dem Nutzer melden
            logger.warning("backup test connection failed: %s", exc)
            return {"ok": False, "message": f"Verbindung fehlgeschlagen: {exc}"}

    # ── Backup ausführen ─────────────────────────────────────────────────────
    def run_backup(self, *, kind: str = "manual") -> BackupRun:
        config = self.get_config()
        run = BackupRun(status="running", kind=kind if kind in ("scheduled", "manual") else "manual")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        tmp_dir = Path(tempfile.mkdtemp(prefix="pm-backup-"))
        try:
            target = _SmbTarget.from_config(config)
            target.validate()

            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            db_dump = tmp_dir / "database.dump"
            self._pg_dump(db_dump)
            storage_archive = tmp_dir / "storage.tar.gz"
            self._archive_storage(storage_archive)

            total_size = db_dump.stat().st_size + storage_archive.stat().st_size
            location = self._upload(target, stamp, [db_dump, storage_archive])
            self._apply_retention(target, int(config.get("retention", 7)))

            run.status = "success"
            run.finished_at = datetime.now().astimezone()
            run.size_bytes = int(total_size)
            run.location = location
            self.db.commit()
            self.db.refresh(run)
            logger.info("backup success run=%s size=%s location=%s", run.id, total_size, location)
            return run
        except Exception as exc:  # noqa: BLE001 - Lauf als fehlgeschlagen protokollieren
            logger.warning("backup failed run=%s: %s", run.id, exc)
            run.status = "failed"
            run.finished_at = datetime.now().astimezone()
            run.error = str(exc)[:2000]
            self.db.commit()
            self.db.refresh(run)
            return run
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── interne Schritte ─────────────────────────────────────────────────────
    @staticmethod
    def _pg_dump(target_path: Path) -> None:
        database_url = settings.database_url
        if not database_url:
            raise RuntimeError("DATABASE_URL ist nicht gesetzt")
        # SQLAlchemy-Treiberzusatz entfernen (pg_dump versteht nur reine URLs).
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        result = subprocess.run(
            ["pg_dump", "--dbname", database_url, "--format", "custom", "--file", str(target_path)],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump fehlgeschlagen: {result.stderr.strip()[:500]}")

    @staticmethod
    def _archive_storage(target_path: Path) -> None:
        storage_root = Path(settings.storage_path)
        with tarfile.open(target_path, "w:gz") as tar:
            if storage_root.is_dir():
                tar.add(storage_root, arcname="storage")

    @staticmethod
    def _upload(target: _SmbTarget, stamp: str, files: list[Path]) -> str:
        with _smb_session(target) as smbclient:
            base_parts = [p for p in (target.folder, stamp) if p]
            dest_dir = _unc(target.host, target.share, *base_parts)
            smbclient.makedirs(dest_dir, exist_ok=True)
            for file_path in files:
                remote = f"{dest_dir}\\{file_path.name}"
                with open(file_path, "rb") as src, smbclient.open_file(remote, mode="wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
            return dest_dir

    @staticmethod
    def _apply_retention(target: _SmbTarget, retention: int) -> None:
        with _smb_session(target) as smbclient:
            root = _unc(target.host, target.share, target.folder) if target.folder else _unc(target.host, target.share)
            names = []
            for entry in smbclient.scandir(root):
                if entry.is_dir():
                    names.append(entry.name)
            for name in select_old_backup_dirs(names, retention):
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
        target = _SmbTarget.from_config(self.get_config())
        target.validate()
        with _smb_session(target) as smbclient:
            root = self._archive_root(target)
            items: list[dict] = []
            for entry in smbclient.scandir(root):
                if not (entry.is_dir() and _BACKUP_DIR_RE.match(entry.name)):
                    continue
                size = 0
                names: set[str] = set()
                try:
                    for f in smbclient.scandir(f"{root}\\{entry.name}"):
                        if not f.is_dir():
                            size += f.stat().st_size
                            names.add(f.name)
                except Exception:  # noqa: BLE001 - unvollständiger Ordner
                    pass
                complete = {"database.dump", "storage.tar.gz"}.issubset(names)
                items.append(
                    {
                        "name": entry.name,
                        "size_bytes": int(size),
                        "created_at": self._archive_created_at(entry.name),
                        "complete": complete,
                    }
                )
            items.sort(key=lambda x: x["name"], reverse=True)
            return items

    def delete_archive(self, name: str) -> None:
        if not _BACKUP_DIR_RE.match(name):
            raise ValueError("Ungültiger Backup-Name")
        target = _SmbTarget.from_config(self.get_config())
        target.validate()
        with _smb_session(target) as smbclient:
            self._smb_rmtree(smbclient, f"{self._archive_root(target)}\\{name}")

    @staticmethod
    def _archive_root(target: _SmbTarget) -> str:
        return _unc(target.host, target.share, target.folder) if target.folder else _unc(target.host, target.share)

    # ── Restore ──────────────────────────────────────────────────────────────
    def restore_archive(self, name: str, *, do_exit: bool = True) -> None:
        """Datenbank und PDF-Speicher aus einem NAS-Backup wiederherstellen.

        Bei Erfolg wird der Prozess beendet, damit der Container neu gegen die
        wiederhergestellte Datenbank startet (saubere Verbindungen/Caches).
        """
        if not _BACKUP_DIR_RE.match(name):
            raise ValueError("Ungültiger Backup-Name")

        target = _SmbTarget.from_config(self.get_config())
        target.validate()
        started = datetime.now().astimezone()
        write_restore_status({"status": "running", "name": name, "started_at": started.isoformat()})

        tmp_dir = Path(tempfile.mkdtemp(prefix="pm-restore-"))
        try:
            db_dump = tmp_dir / "database.dump"
            storage_archive = tmp_dir / "storage.tar.gz"
            self._download(target, name, "database.dump", db_dump)
            self._download(target, name, "storage.tar.gz", storage_archive)

            self._pg_restore(db_dump)
            self._restore_storage(storage_archive)

            write_restore_status(
                {
                    "status": "success",
                    "name": name,
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now().astimezone().isoformat(),
                }
            )
            logger.info("restore success name=%s", name)
        except Exception as exc:  # noqa: BLE001 - Fehler im Status protokollieren
            write_restore_status(
                {
                    "status": "failed",
                    "name": name,
                    "error": str(exc)[:2000],
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now().astimezone().isoformat(),
                }
            )
            logger.warning("restore failed name=%s: %s", name, exc)
            raise
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        if do_exit:
            _schedule_process_exit()

    @staticmethod
    def _download(target: _SmbTarget, name: str, filename: str, dest: Path) -> None:
        with _smb_session(target) as smbclient:
            parts = [p for p in (target.folder, name) if p]
            remote = _unc(target.host, target.share, *parts, filename)
            with smbclient.open_file(remote, mode="rb") as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)

    @staticmethod
    def _terminate_other_connections(database_url: str) -> None:
        """Fremde DB-Verbindungen trennen, damit pg_restore --clean nicht blockiert."""
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

    @staticmethod
    def _pg_restore(dump_path: Path) -> None:
        database_url = settings.database_url
        if not database_url:
            raise RuntimeError("DATABASE_URL ist nicht gesetzt")
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        BackupService._terminate_other_connections(database_url)
        result = subprocess.run(
            [
                "pg_restore",
                "--dbname",
                database_url,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                str(dump_path),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        # pg_restore liefert oft returncode!=0 wegen ignorierbarer Hinweise.
        # Als echten Fehler werten wir nur Zeilen mit "error:".
        if result.returncode != 0:
            fatal = [ln for ln in result.stderr.splitlines() if "error:" in ln.lower()]
            if fatal:
                raise RuntimeError("pg_restore fehlgeschlagen: " + " | ".join(fatal[:5])[:500])

    @staticmethod
    def _restore_storage(archive_path: Path) -> None:
        storage_root = Path(settings.storage_path)
        storage_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pm-storage-") as td:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(td, filter="data")
            src = Path(td) / "storage"
            if not src.is_dir():
                src = Path(td)
            # vorhandenen Speicher leeren …
            for child in storage_root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            # … und durch den Backup-Stand ersetzen.
            for child in src.iterdir():
                dest = storage_root / child.name
                if child.is_dir():
                    shutil.copytree(child, dest)
                else:
                    shutil.copy2(child, dest)
