from __future__ import annotations

import fcntl
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings


MAX_NOTE_AUDIO_CHARS = 60_000
FAILED_VISIBILITY = timedelta(hours=24)
DONE_VISIBILITY = timedelta(days=7)
_DIR_NAME = ".note-audio-jobs"
_SAFE_FILENAME = re.compile(r"[^\w .()-]+", re.UNICODE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _parse_time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class NoteAudioJobStore:
    """Persistent queue shared by the API and worker through STORAGE_PATH."""

    def __init__(self, root: str | Path | None = None) -> None:
        storage = Path(root or get_settings().storage_path).resolve()
        self.root = storage / _DIR_NAME
        self.root.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, job_id: uuid.UUID | str) -> Path:
        return self.root / f"{uuid.UUID(str(job_id))}.json"

    def output_path(self, job_id: uuid.UUID | str) -> Path:
        return self.root / f"{uuid.UUID(str(job_id))}.wav"

    @contextmanager
    def _lock(self, name: str = "queue") -> Iterator[None]:
        path = self.root / f".{name}.lock"
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_path(self, path: Path) -> dict | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _write(self, payload: dict) -> None:
        path = self._meta_path(payload["id"])
        temp = path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temp, path)

    def _all(self) -> list[dict]:
        items = [payload for path in self.root.glob("*.json") if (payload := self._read_path(path))]
        return sorted(items, key=lambda item: str(item.get("created_at") or ""))

    @staticmethod
    def _filename(title: str) -> str:
        cleaned = _SAFE_FILENAME.sub("_", " ".join(str(title or "").split())).strip(" ._")
        return f"{(cleaned[:120] or 'Notiz')}.wav"

    def create(
        self,
        *,
        owner_id: uuid.UUID,
        note_id: uuid.UUID,
        note_title: str,
        text: str,
        voice: str,
        language_mode: str = "auto",
    ) -> dict:
        now = _iso()
        with self._lock():
            for existing in self._all():
                if (
                    existing.get("owner_id") == str(owner_id)
                    and existing.get("note_id") == str(note_id)
                    and existing.get("status") in {"queued", "running"}
                ):
                    return existing
            payload = {
                "id": str(uuid.uuid4()),
                "owner_id": str(owner_id),
                "note_id": str(note_id),
                "note_title": str(note_title or "").strip() or "Ohne Titel",
                "filename": self._filename(note_title),
                "text": text,
                "voice": voice,
                "language_mode": language_mode,
                "status": "queued",
                "progress": 0,
                "phase": "Wartet auf Verarbeitung",
                "error_message": None,
                "cancel_requested": False,
                "worker_id": None,
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "finished_at": None,
            }
            self._write(payload)
            return payload

    def get(self, job_id: uuid.UUID | str, *, owner_id: uuid.UUID | None = None) -> dict | None:
        payload = self._read_path(self._meta_path(job_id))
        if payload is None or (owner_id is not None and payload.get("owner_id") != str(owner_id)):
            return None
        return payload

    def activity(self, owner_id: uuid.UUID) -> list[dict]:
        now = _now()
        visible: list[dict] = []
        for payload in self._all():
            if payload.get("owner_id") != str(owner_id):
                continue
            status = payload.get("status")
            updated = _parse_time(payload.get("updated_at")) or now
            if status in {"queued", "running"}:
                visible.append(payload)
            elif status == "failed" and now - updated <= FAILED_VISIBILITY:
                visible.append(payload)
            elif status == "done" and now - updated <= DONE_VISIBILITY:
                visible.append(payload)
        rank = {"running": 0, "queued": 1, "done": 2, "failed": 3}
        return sorted(visible, key=lambda item: (rank.get(str(item.get("status")), 9), item.get("created_at", "")))

    def claim_next(self, worker_id: str) -> dict | None:
        with self._lock():
            self._purge_expired_unlocked()
            for payload in self._all():
                if payload.get("status") != "queued":
                    continue
                if payload.get("cancel_requested"):
                    self._delete_unlocked(payload)
                    continue
                now = _iso()
                payload.update(
                    status="running", progress=1, phase="Sprachmodell wird vorbereitet",
                    worker_id=worker_id, started_at=payload.get("started_at") or now,
                    updated_at=now, error_message=None,
                )
                self._write(payload)
                return payload
        return None

    def update(self, job_id: uuid.UUID | str, **changes) -> dict | None:
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None:
                return None
            payload.update(changes)
            payload["updated_at"] = _iso()
            self._write(payload)
            return payload

    def complete(self, job_id: uuid.UUID | str, incoming_path: Path) -> bool:
        """Publish WAV and terminal metadata atomically with respect to cancel."""
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None or payload.get("cancel_requested"):
                incoming_path.unlink(missing_ok=True)
                return False
            os.replace(incoming_path, self.output_path(job_id))
            payload.update(
                status="done", progress=100, phase="Bereit zum Herunterladen",
                finished_at=_iso(), worker_id=None, updated_at=_iso(),
            )
            self._write(payload)
            return True

    def cancel(self, job_id: uuid.UUID | str, owner_id: uuid.UUID) -> bool:
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None or payload.get("owner_id") != str(owner_id):
                return False
            if payload.get("status") == "queued":
                payload.update(status="failed", error_message="Vom Nutzer beendet", phase="Beendet", finished_at=_iso(), updated_at=_iso())
                self._write(payload)
            elif payload.get("status") == "running":
                payload["cancel_requested"] = True
                payload["phase"] = "Wird abgebrochen"
                payload["updated_at"] = _iso()
                self._write(payload)
            else:
                return False
            return True

    def restart(self, job_id, owner_id):
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None or payload.get("owner_id") != str(owner_id):
                return None
            if payload.get("status") == "running":
                payload.update(cancel_requested=True, restart_requested=True, phase="Wird neu gestartet", updated_at=_iso())
            else:
                payload.update(status="queued", progress=0, error_message=None, cancel_requested=False,
                               phase="Wartet auf Verarbeitung", worker_id=None, started_at=None, finished_at=None, updated_at=_iso())
            self._write(payload)
            return payload

    def finish_cancel(self, job_id):
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None:
                return
            restart = payload.pop("restart_requested", False)
            payload.update(status="queued" if restart else "failed", progress=0,
                           error_message=None if restart else "Vom Nutzer beendet",
                           phase="Wartet auf Verarbeitung" if restart else "Beendet",
                           cancel_requested=False, worker_id=None, started_at=None,
                           finished_at=None if restart else _iso(), updated_at=_iso())
            self._write(payload)

    def retry(self, job_id: uuid.UUID | str, owner_id: uuid.UUID) -> dict | None:
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None or payload.get("owner_id") != str(owner_id) or payload.get("status") != "failed":
                return None
            self.output_path(job_id).unlink(missing_ok=True)
            payload.update(
                status="queued", progress=0, phase="Wartet auf Verarbeitung", error_message=None,
                cancel_requested=False, worker_id=None, started_at=None, finished_at=None, updated_at=_iso(),
            )
            self._write(payload)
            return payload

    def dismiss(self, job_id: uuid.UUID | str, owner_id: uuid.UUID) -> bool:
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is None or payload.get("owner_id") != str(owner_id) or payload.get("status") not in {"done", "failed"}:
                return False
            self._delete_unlocked(payload)
            return True

    def acknowledge_download(self, job_id: uuid.UUID | str, owner_id: uuid.UUID) -> bool:
        """Remove a completed export after the browser received its audio file."""
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if (
                payload is None
                or payload.get("owner_id") != str(owner_id)
                or payload.get("status") != "done"
            ):
                return False
            self._delete_unlocked(payload)
            return True

    def is_cancel_requested(self, job_id: uuid.UUID | str) -> bool:
        payload = self._read_path(self._meta_path(job_id))
        return payload is None or bool(payload.get("cancel_requested"))

    def remove(self, job_id: uuid.UUID | str) -> None:
        with self._lock(str(job_id)):
            payload = self._read_path(self._meta_path(job_id))
            if payload is not None:
                self._delete_unlocked(payload)

    def reclaim_running(self) -> int:
        reclaimed = 0
        with self._lock():
            for payload in self._all():
                if payload.get("status") != "running":
                    continue
                if payload.get("cancel_requested"):
                    self._delete_unlocked(payload)
                    continue
                payload.update(status="queued", progress=0, phase="Wartet auf Verarbeitung", worker_id=None, updated_at=_iso())
                self._write(payload)
                reclaimed += 1
        return reclaimed

    def _delete_unlocked(self, payload: dict) -> None:
        self.output_path(payload["id"]).unlink(missing_ok=True)
        self._meta_path(payload["id"]).unlink(missing_ok=True)

    def _purge_expired_unlocked(self) -> None:
        cutoff = _now() - DONE_VISIBILITY
        for payload in self._all():
            if payload.get("status") not in {"done", "failed"}:
                continue
            updated = _parse_time(payload.get("updated_at"))
            if updated is not None and updated < cutoff:
                self._delete_unlocked(payload)


note_audio_jobs = NoteAudioJobStore()
