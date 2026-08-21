import unittest
import uuid

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models.scanner import ScannerDevice
from app.models.user import User
from app.schemas.scanners import ScannerDeviceConfigureRequest
from app.services.scanners import ScannerService, scanner_device_key_for_uri
from app.worker import main as worker_main


class ScannerDiscoveryTest(unittest.TestCase):
    def test_inventory_parser_normalizes_and_deduplicates_devices(self) -> None:
        payload = (
            "pixma:04A91912_ABC\tCanon   LiDE 400 scanner\n"
            "airscan:e0:Office\tOffice Scanner\n"
            "pixma:04A91912_ABC\tDuplicate\n"
            "invalid line without separator\n"
            "uri with spaces\tInvalid\n"
        )

        self.assertEqual(
            worker_main._parse_scanner_inventory(payload),
            [
                ("pixma:04A91912_ABC", "Canon LiDE 400 scanner"),
                ("airscan:e0:Office", "Office Scanner"),
            ],
        )

    def test_device_key_is_stable_and_filename_safe(self) -> None:
        uri = "pixma:04A91912_ABC"
        first = scanner_device_key_for_uri(uri)
        second = scanner_device_key_for_uri(uri)
        self.assertEqual(first, second)
        self.assertRegex(first, r"^sane-[0-9a-f]{24}$")

        display_name, parsed_key = worker_main._extract_scanner_device_key(
            f"Scan-20260820__pmdev-{first.removeprefix('sane-')}.pdf"
        )
        self.assertEqual(display_name, "Scan-20260820.pdf")
        self.assertEqual(parsed_key, first)


def _schema_ready() -> bool:
    try:
        with engine.connect() as connection:
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


@unittest.skipUnless(_schema_ready(), "DB nicht migriert/erreichbar – Discovery-Test übersprungen.")
class ScannerDiscoveryDatabaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.uri = f"pixma:test-{uuid.uuid4().hex}"
        self.user = User(
            username=f"scanner-discovery-{uuid.uuid4().hex[:8]}",
            password_hash="x",
            is_admin=True,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        scanner = self.db.query(ScannerDevice).filter(ScannerDevice.connection_uri == self.uri).one_or_none()
        if scanner is not None:
            self.db.execute(
                text("DELETE FROM scanner_device_recipients WHERE scanner_device_id = :scanner_id"),
                {"scanner_id": scanner.id},
            )
            self.db.delete(scanner)
        self.db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": self.user.id})
        self.db.commit()
        self.db.close()

    def test_discovered_device_can_be_configured(self) -> None:
        service = ScannerService(self.db)
        self.assertEqual(service.sync_discovered_devices([(self.uri, "Test Scanner")]), 1)
        scanner = service.get_by_connection_uri(self.uri)
        self.assertIsNotNone(scanner)
        self.assertFalse(scanner.configured)
        self.assertFalse(scanner.enabled)

        result = service.configure_device(
            scanner.id,
            ScannerDeviceConfigureRequest(
                name="Posteingang",
                enabled=True,
                recipient_user_ids=[self.user.id],
            ),
        )
        self.assertTrue(result.configured)
        self.assertTrue(result.enabled)
        self.assertTrue(result.available)
        self.assertEqual(result.name, "Posteingang")
        self.assertEqual([recipient.id for recipient in result.recipients], [self.user.id])

        removed = service.remove_device_configuration(scanner.id)
        self.assertFalse(removed.configured)
        self.assertFalse(removed.enabled)
        self.assertTrue(removed.available)
        self.assertEqual(removed.name, "Test Scanner")
        self.assertEqual(removed.recipients, [])

        restored = service.configure_device(
            scanner.id,
            ScannerDeviceConfigureRequest(name="Wieder hinzugefügt", enabled=True),
        )
        self.assertTrue(restored.configured)
        self.assertTrue(restored.enabled)
        self.assertEqual(restored.name, "Wieder hinzugefügt")


if __name__ == "__main__":
    unittest.main()
