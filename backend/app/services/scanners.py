import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.scanner import ScannerDevice, ScannerDeviceRecipient
from app.models.user import User
from app.schemas.auth import UserRead
from app.schemas.scanners import (
    ScannerDeviceCreateRequest,
    ScannerDeviceListResponse,
    ScannerDeviceRead,
    ScannerDeviceUpdateRequest,
)
from app.services.utils import is_unique_violation


def normalize_scanner_device_key(raw: str | None) -> str:
    return " ".join(str(raw or "").split()).strip()


class ScannerService:
    def __init__(self, db: Session):
        self.db = db

    def _recipients_for(self, scanner_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[UserRead]]:
        if not scanner_ids:
            return {}
        rows = self.db.execute(
            select(ScannerDeviceRecipient.scanner_device_id, User)
            .join(User, User.id == ScannerDeviceRecipient.user_id)
            .where(ScannerDeviceRecipient.scanner_device_id.in_(scanner_ids))
            .order_by(func.lower(User.username).asc(), User.created_at.asc())
        ).all()
        result: dict[uuid.UUID, list[UserRead]] = {scanner_id: [] for scanner_id in scanner_ids}
        for scanner_id, user in rows:
            result.setdefault(scanner_id, []).append(UserRead.model_validate(user, from_attributes=True))
        return result

    def _read(self, scanner: ScannerDevice, recipients: list[UserRead] | None = None) -> ScannerDeviceRead:
        return ScannerDeviceRead(
            id=scanner.id,
            device_key=scanner.device_key,
            name=scanner.name,
            enabled=scanner.enabled,
            live_page_mode=scanner.live_page_mode,
            created_at=scanner.created_at,
            updated_at=scanner.updated_at,
            last_seen_at=scanner.last_seen_at,
            recipients=recipients or [],
        )

    def list_devices(self) -> ScannerDeviceListResponse:
        scanners = list(
            self.db.scalars(select(ScannerDevice).order_by(func.lower(ScannerDevice.name).asc())).all()
        )
        recipients = self._recipients_for([scanner.id for scanner in scanners])
        return ScannerDeviceListResponse(
            items=[self._read(scanner, recipients.get(scanner.id, [])) for scanner in scanners]
        )

    def get_by_key(self, device_key: str) -> ScannerDevice | None:
        normalized = normalize_scanner_device_key(device_key)
        if not normalized:
            return None
        return self.db.scalar(select(ScannerDevice).where(ScannerDevice.device_key == normalized))

    def get_or_create_for_worker(self, device_key: str, *, name: str | None = None) -> ScannerDevice:
        normalized_key = normalize_scanner_device_key(device_key)
        display_name = normalize_scanner_device_key(name) or normalized_key
        scanner = self.get_by_key(normalized_key)
        now = datetime.now(timezone.utc)
        if scanner is not None:
            scanner.last_seen_at = now
            scanner.updated_at = now
            self.db.flush()
            return scanner

        scanner = ScannerDevice(
            device_key=normalized_key,
            name=display_name,
            enabled=True,
            last_seen_at=now,
        )
        self.db.add(scanner)
        self.db.flush()
        return scanner

    def _set_recipients(self, scanner_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
        normalized_ids = []
        seen = set()
        for user_id in user_ids:
            if user_id in seen:
                continue
            seen.add(user_id)
            normalized_ids.append(user_id)

        if normalized_ids:
            active_count = self.db.scalar(
                select(func.count(User.id)).where(User.id.in_(normalized_ids), User.is_active.is_(True))
            )
            if int(active_count or 0) != len(normalized_ids):
                raise NotFoundError("One or more scanner recipient users were not found")

        self.db.execute(delete(ScannerDeviceRecipient).where(ScannerDeviceRecipient.scanner_device_id == scanner_id))
        for user_id in normalized_ids:
            self.db.add(ScannerDeviceRecipient(scanner_device_id=scanner_id, user_id=user_id))

    def create_device(self, payload: ScannerDeviceCreateRequest) -> ScannerDeviceRead:
        scanner = ScannerDevice(
            device_key=normalize_scanner_device_key(payload.device_key),
            name=normalize_scanner_device_key(payload.name),
            enabled=payload.enabled,
        )
        self.db.add(scanner)
        try:
            self.db.flush()
            self._set_recipients(scanner.id, payload.recipient_user_ids)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Scanner device key already exists", details={"device_key": payload.device_key}) from exc
            raise
        self.db.refresh(scanner)
        recipients = self._recipients_for([scanner.id]).get(scanner.id, [])
        return self._read(scanner, recipients)

    def update_device(self, scanner_id: uuid.UUID, payload: ScannerDeviceUpdateRequest) -> ScannerDeviceRead:
        scanner = self.db.get(ScannerDevice, scanner_id)
        if scanner is None:
            raise NotFoundError("Scanner device not found", details={"scanner_id": str(scanner_id)})

        if payload.name is not None:
            scanner.name = normalize_scanner_device_key(payload.name)
        if payload.enabled is not None:
            scanner.enabled = bool(payload.enabled)
        if payload.live_page_mode is not None:
            scanner.live_page_mode = bool(payload.live_page_mode)
        scanner.updated_at = datetime.now(timezone.utc)
        if payload.recipient_user_ids is not None:
            self._set_recipients(scanner.id, payload.recipient_user_ids)

        self.db.commit()
        self.db.refresh(scanner)
        recipients = self._recipients_for([scanner.id]).get(scanner.id, [])
        return self._read(scanner, recipients)
