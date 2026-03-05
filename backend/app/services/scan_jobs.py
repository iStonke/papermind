from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

ScanJobState = Literal["receiving", "processing", "ready", "error"]
ScanJobStep = Literal["convert", "detect", "warp", "clean", "pdf"]


@dataclass
class ScanJobRecord:
    job_id: str
    session_id: str | None = None
    token: str | None = None
    state: ScanJobState = "receiving"
    step: ScanJobStep = "convert"
    progress: float = 0.0
    pages_total: int = 0
    pages_done: int = 0
    recent_files: list[str] = field(default_factory=list)
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clamp_progress(value: float | int) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = 0.0
    return max(0.0, min(1.0, parsed))


def _clamp_count(value: int | float) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = 0
    return max(0, parsed)


class _ScanJobStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, ScanJobRecord] = {}

    def ensure_job(self, job_id: str, *, pages_total: int = 0, session_id: str | None = None, token: str | None = None) -> ScanJobRecord:
        normalized = str(job_id or "").strip()
        if not normalized:
            raise ValueError("job_id is required")
        with self._lock:
            existing = self._jobs.get(normalized)
            if existing:
                return copy.deepcopy(existing)
            created = ScanJobRecord(
                job_id=normalized,
                pages_total=_clamp_count(pages_total),
                session_id=(str(session_id or "").strip() or None),
                token=(str(token or "").strip() or None),
            )
            self._jobs[normalized] = created
            return copy.deepcopy(created)

    def get_job(self, job_id: str) -> ScanJobRecord | None:
        normalized = str(job_id or "").strip()
        if not normalized:
            return None
        with self._lock:
            job = self._jobs.get(normalized)
            if not job:
                return None
            return copy.deepcopy(job)

    def upsert_job(
        self,
        job_id: str,
        *,
        session_id: str | None = None,
        token: str | None = None,
        state: ScanJobState | None = None,
        step: ScanJobStep | None = None,
        progress: float | int | None = None,
        pages_total: int | None = None,
        pages_done: int | None = None,
        error: str | None = None,
    ) -> ScanJobRecord:
        normalized = str(job_id or "").strip()
        if not normalized:
            raise ValueError("job_id is required")
        with self._lock:
            job = self._jobs.get(normalized)
            if not job:
                job = ScanJobRecord(job_id=normalized)
                self._jobs[normalized] = job
            if session_id is not None:
                job.session_id = str(session_id).strip() or None
            if token is not None:
                job.token = str(token).strip() or None
            if state:
                job.state = state
            if step:
                job.step = step
            if progress is not None:
                job.progress = _clamp_progress(progress)
            if pages_total is not None:
                job.pages_total = _clamp_count(pages_total)
            if pages_done is not None:
                job.pages_done = _clamp_count(pages_done)
            if job.pages_total > 0 and job.pages_done > job.pages_total:
                job.pages_done = job.pages_total
            if error is not None:
                clean_error = str(error).strip()
                job.error = clean_error[:500] if clean_error else None
            job.updated_at = _now_utc()
            return copy.deepcopy(job)

    def add_recent_file(self, job_id: str, filename: str, *, max_items: int = 20) -> ScanJobRecord:
        normalized = str(job_id or "").strip()
        if not normalized:
            raise ValueError("job_id is required")
        clean_name = str(filename or "").strip() or "Unbenannt"
        with self._lock:
            job = self._jobs.get(normalized)
            if not job:
                job = ScanJobRecord(job_id=normalized)
                self._jobs[normalized] = job
            job.recent_files.insert(0, clean_name[:240])
            limit = max(1, int(max_items))
            if len(job.recent_files) > limit:
                del job.recent_files[limit:]
            job.updated_at = _now_utc()
            return copy.deepcopy(job)

    def fail_job(self, job_id: str, error_message: str) -> ScanJobRecord:
        return self.upsert_job(
            job_id,
            state="error",
            progress=1.0,
            error=str(error_message or "Verarbeitung fehlgeschlagen."),
        )


_STORE = _ScanJobStore()


def ensure_job(job_id: str, *, pages_total: int = 0, session_id: str | None = None, token: str | None = None) -> ScanJobRecord:
    return _STORE.ensure_job(job_id, pages_total=pages_total, session_id=session_id, token=token)


def get_job(job_id: str) -> ScanJobRecord | None:
    return _STORE.get_job(job_id)


def upsert_job(
    job_id: str,
    *,
    session_id: str | None = None,
    token: str | None = None,
    state: ScanJobState | None = None,
    step: ScanJobStep | None = None,
    progress: float | int | None = None,
    pages_total: int | None = None,
    pages_done: int | None = None,
    error: str | None = None,
) -> ScanJobRecord:
    return _STORE.upsert_job(
        job_id,
        session_id=session_id,
        token=token,
        state=state,
        step=step,
        progress=progress,
        pages_total=pages_total,
        pages_done=pages_done,
        error=error,
    )


def add_recent_file(job_id: str, filename: str, *, max_items: int = 20) -> ScanJobRecord:
    return _STORE.add_recent_file(job_id, filename, max_items=max_items)


def fail_job(job_id: str, error_message: str) -> ScanJobRecord:
    return _STORE.fail_job(job_id, error_message)
