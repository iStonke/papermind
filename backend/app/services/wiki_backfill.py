"""Resumable, low-priority background backfill for the versioned LLM wiki."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.document import Document
from app.models.wiki import WikiBackfillRun
from app.services.wiki import WikiService


logger = logging.getLogger("papermind.wiki.backfill")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clear_lease(run: WikiBackfillRun) -> None:
    run.worker_id = None
    run.lease_token = None
    run.heartbeat_at = None
    run.lease_expires_at = None
    run.current_document_id = None


class WikiBackfillService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def latest(self) -> WikiBackfillRun | None:
        if self.owner_id is None:
            return None
        return self.db.execute(
            select(WikiBackfillRun)
            .where(WikiBackfillRun.owner_id == self.owner_id)
            .order_by(WikiBackfillRun.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def enqueue(self, *, batch_size: int = 1, document_limit: int | None = None) -> WikiBackfillRun:
        if self.owner_id is None:
            raise ValueError("owner_id is required")
        active = self.db.execute(
            select(WikiBackfillRun).where(
                WikiBackfillRun.owner_id == self.owner_id,
                WikiBackfillRun.status.in_(("queued", "running", "paused")),
            )
        ).scalar_one_or_none()
        if active is not None:
            return active

        snapshot_at = _now_utc()
        total = int(
            self.db.scalar(
                select(func.count()).select_from(Document).where(
                    Document.owner_id == self.owner_id,
                    Document.is_deleted.is_(False),
                    Document.embedding_status == "done",
                    Document.created_at <= snapshot_at,
                )
            )
            or 0
        )
        bounded_limit = max(1, min(int(document_limit), 5000)) if document_limit is not None else None
        run = WikiBackfillRun(
            owner_id=self.owner_id,
            status="queued",
            batch_size=max(1, min(int(batch_size), 50)),
            document_limit=bounded_limit,
            snapshot_at=snapshot_at,
            total_documents=min(total, bounded_limit) if bounded_limit is not None else total,
        )
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            active = self.db.execute(
                select(WikiBackfillRun).where(
                    WikiBackfillRun.owner_id == self.owner_id,
                    WikiBackfillRun.status.in_(("queued", "running", "paused")),
                )
            ).scalar_one_or_none()
            if active is not None:
                return active
            raise
        self.db.refresh(run)
        logger.info(
            "wiki backfill queued run_id=%s owner_id=%s total=%s document_limit=%s",
            run.id,
            self.owner_id,
            run.total_documents,
            run.document_limit,
        )
        return run

    def control(self, run_id: uuid.UUID, *, action: str) -> WikiBackfillRun:
        if self.owner_id is None:
            raise ValueError("owner_id is required")
        run = self.db.execute(
            select(WikiBackfillRun)
            .where(WikiBackfillRun.id == run_id, WikiBackfillRun.owner_id == self.owner_id)
            .with_for_update()
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Wiki backfill not found", details={"run_id": str(run_id)})

        if action == "pause":
            if run.status in {"queued", "running"}:
                run.status = "paused"
                _clear_lease(run)
            elif run.status != "paused":
                raise ConflictError("Only an active wiki backfill can be paused")
        elif action == "resume":
            if run.status == "paused":
                run.status = "queued"
                run.finished_at = None
                _clear_lease(run)
            elif run.status not in {"queued", "running"}:
                raise ConflictError("Only a paused wiki backfill can be resumed")
        elif action == "cancel":
            if run.status in {"queued", "running", "paused"}:
                run.status = "cancelled"
                run.finished_at = _now_utc()
                _clear_lease(run)
            elif run.status != "cancelled":
                raise ConflictError("Only an active or paused wiki backfill can be cancelled")
        else:
            raise ValueError(f"unsupported wiki backfill action: {action}")

        run.updated_at = _now_utc()
        self.db.commit()
        self.db.refresh(run)
        logger.info("wiki backfill controlled run_id=%s owner_id=%s action=%s status=%s", run.id, self.owner_id, action, run.status)
        return run

    @staticmethod
    def claim_next(db: Session, *, worker_id: str, lease_seconds: int) -> tuple[uuid.UUID, uuid.UUID] | None:
        now = _now_utc()
        run = db.execute(
            select(WikiBackfillRun)
            .where(
                or_(
                    WikiBackfillRun.status == "queued",
                    and_(
                        WikiBackfillRun.status == "running",
                        WikiBackfillRun.lease_expires_at.isnot(None),
                        WikiBackfillRun.lease_expires_at < now,
                    ),
                )
            )
            .order_by(WikiBackfillRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalar_one_or_none()
        if run is None:
            return None
        token = uuid.uuid4()
        run.status = "running"
        run.started_at = run.started_at or now
        run.worker_id = worker_id
        run.lease_token = token
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=max(30, lease_seconds))
        run.error_message = None
        db.commit()
        return run.id, token

    @staticmethod
    def heartbeat(
        db: Session,
        run_id: uuid.UUID,
        lease_token: uuid.UUID,
        *,
        lease_seconds: int,
    ) -> bool:
        run = db.execute(
            select(WikiBackfillRun).where(
                WikiBackfillRun.id == run_id,
                WikiBackfillRun.status == "running",
                WikiBackfillRun.lease_token == lease_token,
            )
        ).scalar_one_or_none()
        if run is None:
            return False
        now = _now_utc()
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=max(30, lease_seconds))
        db.commit()
        return True

    @staticmethod
    def _documents_after_cursor(db: Session, run: WikiBackfillRun) -> list[Document]:
        if run.processed_documents >= run.total_documents:
            return []
        stmt = select(Document).where(
            Document.owner_id == run.owner_id,
            Document.is_deleted.is_(False),
            Document.embedding_status == "done",
            Document.created_at <= run.snapshot_at,
        )
        if run.cursor_created_at is not None and run.cursor_document_id is not None:
            stmt = stmt.where(
                or_(
                    Document.created_at > run.cursor_created_at,
                    and_(
                        Document.created_at == run.cursor_created_at,
                        Document.id > run.cursor_document_id,
                    ),
                )
            )
        return list(
            db.execute(
                # Exactly one document per lease is intentional. Returning to
                # the worker loop after every document gives OCR, indexing,
                # scanner imports and user work a chance to run immediately.
                stmt.order_by(Document.created_at.asc(), Document.id.asc()).limit(1)
            ).scalars()
        )

    @staticmethod
    def process_claimed_batch(db: Session, run_id: uuid.UUID, lease_token: uuid.UUID) -> WikiBackfillRun | None:
        run = db.execute(
            select(WikiBackfillRun).where(
                WikiBackfillRun.id == run_id,
                WikiBackfillRun.status == "running",
                WikiBackfillRun.lease_token == lease_token,
            )
        ).scalar_one_or_none()
        if run is None:
            return None
        documents = WikiBackfillService._documents_after_cursor(db, run)
        if not documents:
            # End the read transaction before taking the short finalization
            # lock. A pause/cancel that won the race must never be overwritten
            # by the worker marking the run as done.
            db.rollback()
            run = db.execute(
                select(WikiBackfillRun)
                .where(
                    WikiBackfillRun.id == run_id,
                    WikiBackfillRun.status == "running",
                    WikiBackfillRun.lease_token == lease_token,
                )
                .with_for_update()
            ).scalar_one_or_none()
            if run is None:
                return None
            WikiService(db, run.owner_id).compact_large_aggregate_pages(commit=False)
            run.status = "done"
            run.finished_at = _now_utc()
            _clear_lease(run)
            db.commit()
            return run

        for document in documents:
            run.current_document_id = document.id
            try:
                result = WikiService(db, run.owner_id).refresh_document(document.id, commit=False)
                run.processed_documents += 1
                run.updated_documents += int(bool(result.get("updated")))
                run.review_proposals += int(result.get("review_proposals") or 0)
                run.cursor_created_at = document.created_at
                run.cursor_document_id = document.id
                run.updated_at = _now_utc()
                db.commit()
            except Exception as exc:  # noqa: BLE001 - one bad document must not stop the cursor
                db.rollback()
                run = db.execute(
                    select(WikiBackfillRun).where(
                        WikiBackfillRun.id == run_id,
                        WikiBackfillRun.status == "running",
                        WikiBackfillRun.lease_token == lease_token,
                    )
                ).scalar_one_or_none()
                if run is None:
                    return None
                run.processed_documents += 1
                run.failed_documents += 1
                run.cursor_created_at = document.created_at
                run.cursor_document_id = document.id
                run.error_message = str(exc)[:2000]
                run.updated_at = _now_utc()
                db.commit()
                logger.exception("wiki backfill document failed run_id=%s document_id=%s", run_id, document.id)

        # Serialize the final status transition with pause/cancel. Whichever
        # transaction obtains this row lock first wins cleanly; neither side
        # can resurrect a cancelled run from a stale ORM object.
        run = db.execute(
            select(WikiBackfillRun)
            .where(
                WikiBackfillRun.id == run_id,
                WikiBackfillRun.status == "running",
                WikiBackfillRun.lease_token == lease_token,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if run is None:
            return None
        remaining = WikiBackfillService._documents_after_cursor(db, run)
        if remaining:
            run.status = "queued"
        else:
            WikiService(db, run.owner_id).compact_large_aggregate_pages(commit=False)
            run.status = "done"
            run.finished_at = _now_utc()
        _clear_lease(run)
        run.updated_at = _now_utc()
        db.commit()
        return run

    @staticmethod
    def mark_failed(db: Session, run_id: uuid.UUID, lease_token: uuid.UUID, reason: str) -> None:
        run = db.execute(
            select(WikiBackfillRun).where(
                WikiBackfillRun.id == run_id,
                WikiBackfillRun.status == "running",
                WikiBackfillRun.lease_token == lease_token,
            )
        ).scalar_one_or_none()
        if run is None:
            return
        run.status = "failed"
        run.error_message = str(reason)[:2000]
        run.finished_at = _now_utc()
        _clear_lease(run)
        db.commit()
