import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.models.import_inbox import ImportInboxItem
from app.schemas.import_staging import (
    ImportInboxClaimResponse,
    ImportInboxDiscardResponse,
    ImportInboxItemRead,
    ImportInboxListResponse,
    ImportInboxUploadResponse,
)
from app.services.import_staging import ImportStagingService


class ImportInboxService:
    def __init__(self, db: Session):
        self.db = db
        self.import_staging_service = ImportStagingService(db)

    def _pending_count(self) -> int:
        return int(
            self.db.scalar(
                select(func.count(ImportInboxItem.id)).where(ImportInboxItem.claimed_at.is_(None))
            )
            or 0
        )

    @staticmethod
    def _read_item(item: ImportInboxItem) -> ImportInboxItemRead:
        return ImportInboxItemRead(
            id=str(item.id),
            source_file_id=str(item.source_file_id),
            original_name=item.original_name,
            page_count=item.page_count,
            client_name=item.client_name,
            created_at=item.created_at,
        )

    def upload(self, files: list[UploadFile], *, client_name: str | None = None) -> ImportInboxUploadResponse:
        staged = self.import_staging_service.upload_sources(files)
        created: list[ImportInboxItem] = []
        normalized_client = str(client_name or "").strip()[:200] or None

        for source in staged.items:
            item = ImportInboxItem(
                source_file_id=uuid.UUID(source.source_file_id),
                original_name=source.original_name,
                page_count=source.page_count,
                client_name=normalized_client,
            )
            self.db.add(item)
            created.append(item)

        self.db.commit()
        for item in created:
            self.db.refresh(item)

        return ImportInboxUploadResponse(
            items=[self._read_item(item) for item in created],
            pending_count=self._pending_count(),
        )

    def ingest_pdf_path(
        self,
        source_path: Path,
        *,
        original_name: str | None = None,
        client_name: str | None = None,
    ) -> ImportInboxUploadResponse:
        path = Path(source_path).resolve()
        filename = str(original_name or path.name or "Scan.pdf").strip() or "Scan.pdf"
        with path.open("rb") as handle:
            upload = UploadFile(filename=filename, file=handle)
            return self.upload([upload], client_name=client_name)

    def list_pending(self, *, limit: int = 50) -> ImportInboxListResponse:
        normalized_limit = max(1, min(int(limit or 50), 200))
        items = list(
            self.db.scalars(
                select(ImportInboxItem)
                .where(ImportInboxItem.claimed_at.is_(None))
                .order_by(ImportInboxItem.created_at.asc())
                .limit(normalized_limit)
            ).all()
        )
        return ImportInboxListResponse(
            items=[self._read_item(item) for item in items],
            pending_count=self._pending_count(),
        )

    def claim(self, item_ids: list[uuid.UUID]) -> ImportInboxClaimResponse:
        normalized_ids = []
        seen = set()
        for item_id in item_ids:
            if item_id in seen:
                continue
            seen.add(item_id)
            normalized_ids.append(item_id)
        if not normalized_ids:
            raise BadRequestError("item_ids is required")

        result = self.db.execute(
            update(ImportInboxItem)
            .where(ImportInboxItem.id.in_(normalized_ids))
            .where(ImportInboxItem.claimed_at.is_(None))
            .values(claimed_at=datetime.now(timezone.utc))
        )
        self.db.commit()
        return ImportInboxClaimResponse(
            claimed=int(result.rowcount or 0),
            pending_count=self._pending_count(),
        )

    def discard(self, item_ids: list[uuid.UUID]) -> ImportInboxDiscardResponse:
        normalized_ids = []
        seen = set()
        for item_id in item_ids:
            if item_id in seen:
                continue
            seen.add(item_id)
            normalized_ids.append(item_id)
        if not normalized_ids:
            raise BadRequestError("item_ids is required")

        items = list(
            self.db.scalars(
                select(ImportInboxItem).where(ImportInboxItem.id.in_(normalized_ids))
            ).all()
        )
        for item in items:
            self.import_staging_service.delete_source_file(str(item.source_file_id))
            self.db.delete(item)

        self.db.commit()
        return ImportInboxDiscardResponse(
            discarded=len(items),
            pending_count=self._pending_count(),
        )
