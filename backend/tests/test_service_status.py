import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from app.services import system_status
from app.services.system_status import _check_ocr, _service_item, _summary_status


class ServiceStatusTest(unittest.TestCase):
    def test_ocr_reports_disabled_when_auto_ocr_is_off(self) -> None:
        item = _check_ocr({"documents": {"auto_ocr": False}, "ocr": {"language": "deu+eng"}})

        self.assertEqual(item.status, "disabled")
        self.assertIs(item.enabled, False)
        self.assertEqual(item.setting_key, "documents.auto_ocr")

    @patch("app.services.system_status.shutil.which")
    def test_ocr_reports_warning_without_ocrmypdf(self, which) -> None:
        which.side_effect = lambda name: "/usr/bin/tesseract" if name == "tesseract" else None

        item = _check_ocr({"documents": {"auto_ocr": True}, "ocr": {"language": "deu+eng"}})

        self.assertEqual(item.status, "warning")
        self.assertIn("ocrmypdf fehlt", item.detail)

    def test_summary_ignores_disabled_services(self) -> None:
        items = [
            _service_item(key="ollama", label="Ollama", description="", status="disabled", enabled=False),
            _service_item(key="backend", label="Backend", description="", status="ok"),
        ]

        self.assertEqual(_summary_status(items), "ok")

    def test_service_actions_expose_check_and_disable_host_control_actions(self) -> None:
        item = _service_item(key="ollama", label="Ollama", description="", status="ok")
        actions = {action.action: action for action in item.actions}

        self.assertTrue(actions["check"].enabled)
        self.assertFalse(actions["start"].enabled)
        self.assertFalse(actions["restart"].enabled)
        self.assertFalse(actions["stop"].enabled)
        self.assertIn("Host-Control", actions["restart"].reason)

    def test_host_metadata_uses_the_minimal_etc_mount(self) -> None:
        with TemporaryDirectory() as directory:
            etc_dir = Path(directory)
            (etc_dir / "hostname").write_text("papermind-pi\n", encoding="utf-8")
            (etc_dir / "os-release").write_text('PRETTY_NAME="Pi OS"\n', encoding="utf-8")
            settings = SimpleNamespace(system_host_etc_path=str(etc_dir), system_sys_path="/missing")
            with patch.object(system_status, "settings", settings):
                host = system_status._collect_host()

        self.assertEqual(host.hostname, "papermind-pi")
        self.assertEqual(host.os, "Pi OS")

    @patch("app.services.system_status._storage_footprint_bytes", return_value=200_000)
    @patch("app.services.system_status.os.statvfs")
    def test_disk_separates_document_and_system_usage(self, statvfs, _footprint) -> None:
        statvfs.return_value = SimpleNamespace(
            f_blocks=1_000,
            f_bfree=250,
            f_bavail=250,
            f_frsize=1_024,
        )

        disk = system_status._disk_for("Dokumente", "/data/storage")

        self.assertIsNotNone(disk)
        self.assertEqual(disk.document_bytes, 200_000)
        self.assertEqual(disk.system_bytes, 568_000)

    @patch("app.services.system_status._storage_footprint_bytes", return_value=900_000)
    @patch("app.services.system_status.os.statvfs")
    def test_disk_footprint_is_capped_to_used_space(self, statvfs, _footprint) -> None:
        statvfs.return_value = SimpleNamespace(
            f_blocks=1_000,
            f_bfree=250,
            f_bavail=250,
            f_frsize=1_024,
        )

        disk = system_status._disk_for("Dokumente", "/data/storage")

        self.assertIsNotNone(disk)
        self.assertEqual(disk.document_bytes, 768_000)
        self.assertEqual(disk.system_bytes, 0)


if __name__ == "__main__":
    unittest.main()
