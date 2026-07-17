import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.models.import_inbox import ImportInboxItem
from app.models.scanner import ScannerDevice, ScannerDeviceRecipient, ScannerScanJob
from app.schemas.import_staging import (
    ImportInboxAssignResponse,
    ImportInboxClaimResponse,
    ImportInboxDiscardPagesResponse,
    ImportInboxDiscardResponse,
    ImportInboxItemRead,
    ImportInboxListResponse,
    ImportInboxUploadResponse,
    ScannerScanJobRead,
    ScannerTriggerInfo,
)
from app.services.import_staging import ImportStagingService
from app.services.import_timing import elapsed_ms, log_import_timing, now_perf
from app.services.scanners import is_scanning_active
from app.services.settings import SettingsService

SCAN_JOB_VISIBLE_STALE_SECONDS = 300


def _normalize_item_ids(item_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    normalized_ids = []
    seen = set()
    for item_id in item_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        normalized_ids.append(item_id)
    if not normalized_ids:
        raise BadRequestError("item_ids is required")
    return normalized_ids


class ImportInboxService:
    def __init__(self, db: Session, owner_id=None):
        self.db = db
        self.owner_id = owner_id
        self.import_staging_service = ImportStagingService(db, owner_id)

    def _owned_scope(self, stmt):
        if self.owner_id is not None:
            return stmt.where(ImportInboxItem.owner_id == self.owner_id)
        return stmt

    def _visible_scanner_condition(self):
        if self.owner_id is None:
            return False
        return and_(
            ImportInboxItem.owner_id.is_(None),
            ImportInboxItem.source_type == "scanner",
            ImportInboxItem.claimed_at.is_(None),
            ImportInboxItem.scanner_device_id.is_not(None),
            exists(
                select(1)
                .select_from(ScannerDeviceRecipient)
                .join(ScannerDevice, ScannerDevice.id == ScannerDeviceRecipient.scanner_device_id)
                .where(ScannerDeviceRecipient.scanner_device_id == ImportInboxItem.scanner_device_id)
                .where(ScannerDeviceRecipient.user_id == self.owner_id)
                .where(ScannerDevice.enabled.is_(True))
            ),
        )

    def _visible_scope(self, stmt):
        if self.owner_id is None:
            return stmt
        return stmt.where(
            or_(
                ImportInboxItem.owner_id == self.owner_id,
                self._visible_scanner_condition(),
            )
        )

    def _pending_count(self) -> int:
        return int(
            self.db.scalar(
                self._visible_scope(select(func.count(ImportInboxItem.id)).where(ImportInboxItem.claimed_at.is_(None)))
            )
            or 0
        )

    def _scanning_active(self) -> bool:
        if self.owner_id is None:
            return False
        scanners = self.db.scalars(
            select(ScannerDevice)
            .join(ScannerDeviceRecipient, ScannerDeviceRecipient.scanner_device_id == ScannerDevice.id)
            .where(ScannerDeviceRecipient.user_id == self.owner_id)
            .where(ScannerDevice.enabled.is_(True))
            .where(ScannerDevice.scanning_since.is_not(None))
        ).all()
        return any(is_scanning_active(scanner) for scanner in scanners)

    def _triggerable_scanner(self) -> ScannerTriggerInfo | None:
        """Der Scanner, den der aktuelle Benutzer aus der UI auslösen darf.

        Single-Pi-Setup: i. d. R. genau ein Scanner. Bei mehreren wird der
        zuletzt gesehene genommen.
        """
        if self.owner_id is None:
            return None
        scanner = self.db.scalars(
            select(ScannerDevice)
            .join(ScannerDeviceRecipient, ScannerDeviceRecipient.scanner_device_id == ScannerDevice.id)
            .where(ScannerDeviceRecipient.user_id == self.owner_id)
            .where(ScannerDevice.enabled.is_(True))
            .order_by(ScannerDevice.last_seen_at.desc().nullslast())
        ).first()
        if scanner is None:
            return None
        # „Seiten sofort senden" ist global (nicht mehr pro Scanner); der
        # Import-Dialog nutzt den Wert, um die Abschluss-Taste ein-/auszublenden.
        live_page_mode = bool(SettingsService(self.db).get_settings().documents.scan_live_page_mode)
        return ScannerTriggerInfo(
            id=scanner.id,
            name=scanner.name,
            live_page_mode=live_page_mode,
            last_seen_at=scanner.last_seen_at,
        )

    def _read_item(self, item: ImportInboxItem) -> ImportInboxItemRead:
        return ImportInboxItemRead(
            id=str(item.id),
            source_file_id=str(item.source_file_id),
            original_name=item.original_name,
            page_count=item.page_count,
            preview_url=self.import_staging_service.source_preview_url(str(item.source_file_id)),
            analysis=self.import_staging_service.get_source_analysis_response(str(item.source_file_id)),
            scan_cleanup=self.import_staging_service.get_source_scan_cleanup_response(str(item.source_file_id)),
            client_name=item.client_name,
            source_type=item.source_type,
            scanner_device_id=str(item.scanner_device_id) if item.scanner_device_id else None,
            is_assigned_to_me=self.owner_id is not None and item.owner_id == self.owner_id,
            created_at=item.created_at,
        )

    def _read_scan_job(self, job: ScannerScanJob) -> ScannerScanJobRead:
        return ScannerScanJobRead(
            id=str(job.id),
            scanner_device_id=str(job.scanner_device_id),
            state=job.state,
            command=job.command,
            source_file_id=str(job.source_file_id) if job.source_file_id else None,
            import_inbox_item_id=str(job.import_inbox_item_id) if job.import_inbox_item_id else None,
            page_count=job.page_count,
            error=job.error,
            error_kind=job.error_kind,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )

    def _active_scan_jobs(self, *, limit: int = 20) -> list[ScannerScanJobRead]:
        if self.owner_id is None:
            return []
        rows = list(
            self.db.scalars(
                select(ScannerScanJob)
                .join(ScannerDevice, ScannerDevice.id == ScannerScanJob.scanner_device_id)
                .join(ScannerDeviceRecipient, ScannerDeviceRecipient.scanner_device_id == ScannerDevice.id)
                .where(ScannerDeviceRecipient.user_id == self.owner_id)
                .where(ScannerDevice.enabled.is_(True))
                # Aktive Jobs IMMER zeigen; Fehlerjobs nur, solange sie frisch
                # sind, damit die UI Timeout/Datei fehlt/Scanner offline melden
                # kann, ohne alte Fehler ewig nachzuhängen.
                .where(ScannerScanJob.state.in_(("queued", "scanning", "processing", "error")))
                .where(ScannerScanJob.updated_at >= datetime.now(timezone.utc) - timedelta(seconds=SCAN_JOB_VISIBLE_STALE_SECONDS))
                .order_by(ScannerScanJob.created_at.asc())
                .limit(max(1, min(int(limit or 20), 50)))
            ).all()
        )
        return [self._read_scan_job(job) for job in rows]

    def upload(
        self,
        files: list[UploadFile],
        *,
        client_name: str | None = None,
        source_type: str = "shortcut",
        scanner_device_id: uuid.UUID | None = None,
        preview_paths: list[Path | None] | None = None,
    ) -> ImportInboxUploadResponse:
        normalized_source_type = str(source_type or "shortcut").strip() or "shortcut"
        if normalized_source_type != "scanner" and self.owner_id is None:
            raise BadRequestError("No user context for import inbox upload")
        if normalized_source_type == "scanner" and scanner_device_id is None:
            raise BadRequestError("scanner_device_id is required for scanner uploads")

        upload_started = now_perf()
        staged = self.import_staging_service.upload_sources(files)
        normalized_preview_paths = list(preview_paths or [])
        created: list[ImportInboxItem] = []
        normalized_client = str(client_name or "").strip()[:200] or None

        for index, source in enumerate(staged.items):
            preview_path = normalized_preview_paths[index] if index < len(normalized_preview_paths) else None
            self.import_staging_service.store_source_preview(source.source_file_id, preview_path)
            item = ImportInboxItem(
                owner_id=None if normalized_source_type == "scanner" else self.owner_id,
                scanner_device_id=scanner_device_id if normalized_source_type == "scanner" else None,
                source_type=normalized_source_type,
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
            log_import_timing(
                "inbox_item_created",
                source_file_id=str(item.source_file_id),
                inbox_item_id=str(item.id),
                source_type=item.source_type,
                scanner_device_id=str(item.scanner_device_id) if item.scanner_device_id else None,
                page_count=item.page_count,
                duration_ms=elapsed_ms(upload_started),
            )

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
        source_type: str = "shortcut",
        scanner_device_id: uuid.UUID | None = None,
        preview_path: Path | None = None,
    ) -> ImportInboxUploadResponse:
        path = Path(source_path).resolve()
        filename = str(original_name or path.name or "Scan.pdf").strip() or "Scan.pdf"
        with path.open("rb") as handle:
            upload = UploadFile(filename=filename, file=handle)
            return self.upload(
                [upload],
                client_name=client_name,
                source_type=source_type,
                scanner_device_id=scanner_device_id,
                preview_paths=[preview_path] if preview_path is not None else None,
            )

    def list_pending(self, *, limit: int = 50) -> ImportInboxListResponse:
        normalized_limit = max(1, min(int(limit or 50), 200))
        items = list(
            self.db.scalars(
                self._visible_scope(
                    select(ImportInboxItem)
                    .where(ImportInboxItem.claimed_at.is_(None))
                    .order_by(ImportInboxItem.created_at.asc())
                    .limit(normalized_limit)
                )
            ).all()
        )
        return ImportInboxListResponse(
            items=[self._read_item(item) for item in items],
            pending_count=self._pending_count(),
            scanning=self._scanning_active(),
            scanner=self._triggerable_scanner(),
            scan_jobs=self._active_scan_jobs(),
        )

    def assign_to_current_user(self, item_ids: list[uuid.UUID]) -> ImportInboxAssignResponse:
        if self.owner_id is None:
            raise BadRequestError("No user context for import inbox assignment")
        normalized_ids = _normalize_item_ids(item_ids)
        result = self.db.execute(
            update(ImportInboxItem)
            .where(ImportInboxItem.id.in_(normalized_ids))
            .where(self._visible_scanner_condition())
            .values(owner_id=self.owner_id)
        )
        self.db.commit()
        return ImportInboxAssignResponse(
            assigned=int(result.rowcount or 0),
            pending_count=self._pending_count(),
        )

    def claim(self, item_ids: list[uuid.UUID]) -> ImportInboxClaimResponse:
        normalized_ids = _normalize_item_ids(item_ids)

        result = self.db.execute(
            self._owned_scope(
                update(ImportInboxItem)
                .where(ImportInboxItem.id.in_(normalized_ids))
                .where(ImportInboxItem.claimed_at.is_(None))
                .values(claimed_at=datetime.now(timezone.utc))
            )
        )
        self.db.commit()
        return ImportInboxClaimResponse(
            claimed=int(result.rowcount or 0),
            pending_count=self._pending_count(),
        )

    def discard(self, item_ids: list[uuid.UUID]) -> ImportInboxDiscardResponse:
        normalized_ids = _normalize_item_ids(item_ids)

        # _visible_scope statt _owned_scope: ein sichtbares, aber noch nicht
        # explizit zugewiesenes Scanner-Item (owner_id NULL) muss verwerfbar
        # sein, ohne vorher zwingend per /assign übernommen worden zu sein -
        # sonst läuft der Discard fehlerfrei durch, löscht aber nichts (0
        # getroffene Zeilen) und das Item taucht nach einem Refresh wieder auf.
        items = list(
            self.db.scalars(
                self._visible_scope(select(ImportInboxItem).where(ImportInboxItem.id.in_(normalized_ids)))
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

    def discard_pages(self, source_file_id: uuid.UUID, page_indices: list[int]) -> ImportInboxDiscardPagesResponse:
        # Wie discard(): _visible_scope, damit ein noch nicht zugewiesenes,
        # aber sichtbares Scanner-Item ebenfalls verwerfbar ist.
        item = self.db.scalar(
            self._visible_scope(select(ImportInboxItem).where(ImportInboxItem.source_file_id == source_file_id))
        )
        if item is None:
            raise BadRequestError("import inbox source was not found")

        remaining_page_count = self.import_staging_service.delete_source_pages(str(source_file_id), page_indices)
        if remaining_page_count <= 0:
            self.db.delete(item)
        else:
            item.page_count = remaining_page_count

        self.db.commit()
        return ImportInboxDiscardPagesResponse(
            source_file_id=str(source_file_id),
            page_count=remaining_page_count,
            pending_count=self._pending_count(),
        )
