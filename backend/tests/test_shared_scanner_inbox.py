"""Integration tests for shared-by-default scanner access."""

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.errors import ForbiddenError
from app.db.session import SessionLocal, engine
from app.models.import_inbox import ImportInboxItem
from app.models.scanner import ScannerDevice, ScannerDeviceRecipient
from app.models.user import User
from app.services.import_inbox import ImportInboxService
from app.services.scanners import ScannerService


_REQUIRED_TABLES = (
    "users",
    "scanner_devices",
    "scanner_device_recipients",
    "import_inbox_items",
)


def _schema_ready() -> bool:
    try:
        with engine.connect() as connection:
            for table in _REQUIRED_TABLES:
                if connection.execute(text("SELECT to_regclass(:table)"), {"table": f"public.{table}"}).scalar() is None:
                    return False
            return bool(
                connection.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'scanner_devices' AND column_name = 'configured')"
                    )
                ).scalar()
            )
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_schema_ready(), "DB nicht migriert/erreichbar – Shared-Inbox-Test übersprungen.")
class SharedScannerInboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        token = uuid.uuid4().hex[:8]
        self.user_a = User(
            username=f"shared-scan-a-{token}",
            password_hash="x",
            is_admin=False,
            is_active=True,
        )
        self.user_b = User(
            username=f"shared-scan-b-{token}",
            password_hash="x",
            is_admin=False,
            is_active=True,
        )
        self.db.add_all([self.user_a, self.user_b])
        self.db.flush()
        self.scanner = ScannerDevice(
            device_key=f"shared-{token}",
            name="Gemeinsamer Scanner",
            configured=True,
            enabled=True,
            last_seen_at=datetime.now(timezone.utc),
        )
        self.db.add(self.scanner)
        self.db.flush()
        self.item = ImportInboxItem(
            owner_id=None,
            scanner_device_id=self.scanner.id,
            source_file_id=uuid.uuid4(),
            source_type="scanner",
            original_name="Gemeinsamer Scan.pdf",
            page_count=1,
        )
        self.db.add(self.item)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.execute(
            text("DELETE FROM import_inbox_items WHERE scanner_device_id = :scanner_id"),
            {"scanner_id": self.scanner.id},
        )
        self.db.execute(
            text("DELETE FROM scanner_scan_commands WHERE scanner_device_id = :scanner_id"),
            {"scanner_id": self.scanner.id},
        )
        self.db.execute(
            text("DELETE FROM scanner_scan_jobs WHERE scanner_device_id = :scanner_id"),
            {"scanner_id": self.scanner.id},
        )
        self.db.execute(
            text("DELETE FROM scanner_device_recipients WHERE scanner_device_id = :scanner_id"),
            {"scanner_id": self.scanner.id},
        )
        self.db.execute(text("DELETE FROM scanner_devices WHERE id = :scanner_id"), {"scanner_id": self.scanner.id})
        self.db.execute(
            text("DELETE FROM users WHERE id IN (:user_a, :user_b)"),
            {"user_a": self.user_a.id, "user_b": self.user_b.id},
        )
        self.db.commit()
        self.db.close()

    def _visible_item_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        service = ImportInboxService(self.db, user_id)
        return set(
            self.db.scalars(
                service._visible_scope(
                    select(ImportInboxItem.id).where(ImportInboxItem.claimed_at.is_(None))
                )
            ).all()
        )

    def test_unrestricted_scan_is_shared_until_one_user_takes_ownership(self) -> None:
        self.assertIsNone(self.item.owner_id)
        inbox_a = ImportInboxService(self.db, self.user_a.id).list_pending()
        inbox_b = ImportInboxService(self.db, self.user_b.id).list_pending()
        self.assertIn(str(self.item.id), {item.id for item in inbox_a.items})
        self.assertIn(str(self.item.id), {item.id for item in inbox_b.items})
        self.assertEqual(str(inbox_a.scanner.id), str(self.scanner.id))
        self.assertEqual(str(inbox_b.scanner.id), str(self.scanner.id))
        self.assertTrue(ScannerService(self.db)._user_can_access_device(self.scanner.id, self.user_a.id))
        self.assertTrue(ScannerService(self.db)._user_can_access_device(self.scanner.id, self.user_b.id))

        assigned = ImportInboxService(self.db, self.user_a.id).assign_to_current_user([self.item.id])
        self.assertEqual(assigned.assigned, 1)
        self.db.refresh(self.item)
        self.assertEqual(self.item.owner_id, self.user_a.id)
        self.assertIn(self.item.id, self._visible_item_ids(self.user_a.id))
        self.assertNotIn(self.item.id, self._visible_item_ids(self.user_b.id))

    def test_recipient_list_turns_shared_scanner_into_restricted_scanner(self) -> None:
        self.db.add(ScannerDeviceRecipient(scanner_device_id=self.scanner.id, user_id=self.user_a.id))
        self.db.commit()

        self.assertIn(self.item.id, self._visible_item_ids(self.user_a.id))
        self.assertNotIn(self.item.id, self._visible_item_ids(self.user_b.id))
        scanner_service = ScannerService(self.db)
        self.assertTrue(scanner_service._user_can_access_device(self.scanner.id, self.user_a.id))
        self.assertFalse(scanner_service._user_can_access_device(self.scanner.id, self.user_b.id))
        with self.assertRaises(ForbiddenError):
            scanner_service.enqueue_scan_command(self.scanner.id, "page", requested_by=self.user_b.id)


if __name__ == "__main__":
    unittest.main()
