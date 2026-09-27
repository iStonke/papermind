"""Unit tests for the host-side streaming scanner preview helper."""

import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


HELPER_PATH = Path(__file__).resolve().parents[2] / "deploy" / "scan-button" / "papermind-live-preview.py"
SPEC = importlib.util.spec_from_file_location("papermind_live_preview", HELPER_PATH)
helper = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(helper)


class ScannerLivePreviewHelperTest(unittest.TestCase):
    def test_partial_header_is_treated_as_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "scan.pnm"
            source.write_bytes(b"P")
            with self.assertRaises(EOFError):
                helper.read_pnm_header(source)

    def test_complete_ppm_becomes_full_size_png_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "scan.pnm"
            preview = root / "preview.png"
            status = root / "preview.status"
            # Vier verschiedenfarbige Zeilen; ein nicht existierender PID lässt
            # den Helfer nach dem ersten vollständigen Render sauber enden.
            pixels = (
                bytes([255, 0, 0]) * 4
                + bytes([0, 255, 0]) * 4
                + bytes([0, 0, 255]) * 4
                + bytes([0, 0, 0]) * 4
            )
            source.write_bytes(b"P6\n4 4\n255\n" + pixels)

            helper.render_loop(source, preview, status, 999_999_999, interval=0.1, max_width=640)

            png = preview.read_bytes()
            self.assertTrue(png.startswith(helper.PNG_SIGNATURE))
            self.assertEqual(struct.unpack(">II", png[16:24]), (4, 4))
            self.assertIn("PROGRESS=100", status.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
