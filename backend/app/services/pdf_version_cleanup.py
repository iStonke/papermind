"""Bounded cleanup of old immutable PDF publications, never current files."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
import re
import stat
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.job import Job
from app.services.maintenance import MaintenanceActive, write_activity

logger = logging.getLogger("papermind.cleanup")
VERSION_NAME = re.compile(r"(?:original|ocr|preview_pdf)-[0-9a-f]{32}\.pdf|thumbnail-[0-9a-f]{32}\.png")


def cleanup_pdf_versions(db, storage_path, *, retention_days=14, max_files=100, now=None):
    """Serialize with publishers and retain references, trash and active jobs."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(1, retention_days))
    root = Path(storage_path).resolve()
    removed = 0
    inspected = 0
    deadline = time.monotonic() + 10
    try:
        with write_activity(wait=False):
            for directory in root.iterdir():
                if time.monotonic() >= deadline or inspected >= 5000 or removed >= max_files:
                    break
                try:
                    document_id = uuid.UUID(directory.name)
                except ValueError:
                    continue
                if directory.name != str(document_id):
                    continue
                if directory.is_symlink() or not directory.is_dir():
                    continue
                # A document row lock excludes reorder/OCR reference publication.
                document = db.execute(select(Document.id, Document.storage_key)
                    .where(Document.id == document_id).with_for_update(skip_locked=True)).first()
                if document is None:
                    continue
                try:
                    if db.scalar(select(Job.id).where(Job.document_id == document_id,
                            Job.status.in_(("queued", "running"))).limit(1)) is not None:
                        continue
                    # Preserve even legacy references belonging to a different
                    # document. Unreferenced means no database reference at all.
                    prefix = directory.name + '/%'
                    references = set(db.scalars(select(DocumentFile.file_key)
                        .where(DocumentFile.file_key.like(prefix))))
                    references.update(db.scalars(select(Document.storage_key)
                        .where(Document.storage_key.like(prefix))))
                    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    try:
                        for name in os.listdir(descriptor):
                            inspected += 1
                            if removed >= max_files or inspected > 5000 or time.monotonic() >= deadline:
                                break
                            if not VERSION_NAME.fullmatch(name) or f"{directory.name}/{name}" in references:
                                continue
                            try:
                                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                                if not stat.S_ISREG(metadata.st_mode) or metadata.st_mtime >= cutoff.timestamp():
                                    continue
                                os.unlink(name, dir_fd=descriptor)
                                removed += 1
                            except FileNotFoundError:
                                continue
                    finally:
                        os.close(descriptor)
                finally:
                    db.rollback()
    except MaintenanceActive:
        return 0
    finally:
        # Release document locks before the worker continues polling.
        db.rollback()
    if removed:
        logger.info("old PDF versions removed count=%s", removed)
    return removed
