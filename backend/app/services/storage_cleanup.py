"""Durable cleanup requests. A live account is never removed from storage."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.models.user import User


def schedule_user_cleanup(owner_id, *, document_ids, file_keys, source_ids) -> Path:
    root = Path(get_settings().storage_path).resolve() / ".storage-cleanup"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.UUID(str(owner_id))}.json"
    payload = {"owner_id": str(owner_id), "document_ids": [str(value) for value in document_ids],
               "file_keys": sorted(file_keys), "source_ids": [str(value) for value in source_ids]}
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary, path)
    return path


def run_user_cleanup(db, path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    owner = uuid.UUID(payload["owner_id"])
    if db.scalar(select(User.id).where(User.id == owner)) is not None:
        return False  # Delete may have failed or a backup may have restored it.
    root = Path(get_settings().storage_path).resolve()

    def remove(relative: str) -> None:
        candidate = root / relative
        resolved = candidate.resolve()
        if resolved == root or root not in resolved.parents:
            raise ValueError("Invalid cleanup path")
        if candidate.is_symlink() or not candidate.is_dir():
            candidate.unlink(missing_ok=True)
        else:
            shutil.rmtree(candidate)

    from app.services.note_audio_jobs import NoteAudioJobStore
    NoteAudioJobStore(root).remove_owner(owner)
    for key in payload["file_keys"]:
        remove(key)
    for document_id in payload["document_ids"]:
        remove(str(uuid.UUID(document_id)))
    for relative in (f"avatars/{owner}.webp", f"note-images/{owner}", f"dossier-images/{owner}"):
        remove(relative)
    sources = {str(uuid.UUID(value)) for value in payload["source_ids"]}
    staging = root / "import_staging"
    # Direct uploads have no inbox row; their owner marker records attribution.
    for marker in staging.glob("*.owner.json"):
        meta = json.loads(marker.read_text(encoding="utf-8"))
        if meta.get("owner_id") == str(owner):
            sources.add(str(uuid.UUID(marker.name.split(".")[0])))
    for source_id in sources:
        for candidate in staging.glob(f"{source_id}.*"):
            remove(str(candidate.relative_to(root)))
    path.unlink(missing_ok=True)
    return True


def retry_user_cleanups(db) -> int:
    import logging
    completed = 0
    root = Path(get_settings().storage_path).resolve() / ".storage-cleanup"
    for path in root.glob("*.json"):
        try:
            completed += int(run_user_cleanup(db, path))
        except Exception:
            logging.getLogger("papermind.cleanup").exception("user cleanup deferred task=%s", path.name)
    return completed
