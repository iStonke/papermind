import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
