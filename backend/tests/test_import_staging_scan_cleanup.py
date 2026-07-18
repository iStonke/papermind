import tempfile
import unittest
import uuid
from types import SimpleNamespace

from PIL import Image

from app.services import import_staging
from app.services.import_staging import ImportStagingService


class ImportStagingScanCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_storage_path = import_staging.settings.storage_path
        import_staging.settings.storage_path = self.temp_dir.name
        self.service = ImportStagingService(db=None)

    def tearDown(self) -> None:
        import_staging.settings.storage_path = self.previous_storage_path
        self.temp_dir.cleanup()

    def test_scan_cleanup_response_roundtrip(self) -> None:
        source_file_id = str(uuid.uuid4())

        self.service._write_source_scan_cleanup(
            source_file_id,
            status="ready",
            mode="bw",
            revision="123",
            duration_ms=42.5,
        )

        response = self.service.get_source_scan_cleanup_response(source_file_id)

        self.assertEqual(response["status"], "ready")
        self.assertEqual(response["mode"], "bw")
        self.assertEqual(response["revision"], "123")
        self.assertEqual(response["duration_ms"], 42.5)

    def test_committed_pages_mode_requires_all_sources_ready(self) -> None:
        first_source_id = str(uuid.uuid4())
        second_source_id = str(uuid.uuid4())
        pages = [
            SimpleNamespace(source_file_id=first_source_id),
            SimpleNamespace(source_file_id=second_source_id),
        ]

        self.service._write_source_scan_cleanup(first_source_id, status="ready", mode="bw")
        self.service._write_source_scan_cleanup(second_source_id, status="running", mode="bw")
        self.assertIsNone(self.service._scan_cleanup_mode_for_committed_pages(pages))

        self.service._write_source_scan_cleanup(second_source_id, status="ready", mode="bw")
        self.assertEqual(self.service._scan_cleanup_mode_for_committed_pages(pages), "bw")

        self.service._write_source_scan_cleanup(second_source_id, status="ready", mode="white")
        self.assertEqual(self.service._scan_cleanup_mode_for_committed_pages(pages), "mixed")

    def test_mark_pending_only_when_cleanup_enabled(self) -> None:
        source_ids = [str(uuid.uuid4()) for _ in range(2)]

        self.service._scan_cleanup_settings = lambda: ("bw", 300)
        self.assertTrue(self.service.mark_scan_cleanup_pending(source_ids))
        for source_id in source_ids:
            self.assertEqual(self.service.get_source_scan_cleanup_response(source_id)["status"], "pending")

        # Bereinigung aus: kein Status, sonst bliebe im Dialog ein Spinner stehen.
        disabled_id = str(uuid.uuid4())
        self.service._scan_cleanup_settings = lambda: (None, 300)
        self.assertFalse(self.service.mark_scan_cleanup_pending([disabled_id]))
        self.assertIsNone(self.service.get_source_scan_cleanup_response(disabled_id))

    def test_regenerate_source_preview_writes_png(self) -> None:
        source_file_id = str(uuid.uuid4())
        source_path = self.service._source_pdf_path(source_file_id)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 850), (255, 255, 255)).save(source_path, format="PDF", resolution=300.0)

        self.service._regenerate_source_preview(source_file_id, source_path)

        preview_path = self.service._source_preview_path(source_file_id)
        self.assertTrue(preview_path.exists())
        with Image.open(preview_path) as preview:
            self.assertEqual(preview.format, "PNG")
            self.assertLessEqual(max(preview.size), import_staging._STAGING_PREVIEW_MAX_LONG_EDGE)
        self.assertFalse(any(preview_path.parent.glob(f"{preview_path.name}.*.tmp")))

    def test_regenerate_source_preview_drops_stale_png_on_failure(self) -> None:
        source_file_id = str(uuid.uuid4())
        source_path = self.service._source_pdf_path(source_file_id)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"not a pdf")
        preview_path = self.service._source_preview_path(source_file_id)
        preview_path.write_bytes(b"stale raw preview")

        self.service._regenerate_source_preview(source_file_id, source_path)

        # Lieber gar keine Vorschau als die des Rohscans.
        self.assertFalse(preview_path.exists())

    def test_delete_scan_cleanup_artifacts(self) -> None:
        source_file_id = str(uuid.uuid4())
        source_path = self.service._source_pdf_path(source_file_id)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        raw_path = self.service._source_raw_pdf_path(source_file_id)
        cleanup_path = self.service._source_scan_cleanup_path(source_file_id)
        temp_path = source_path.with_name(f"{source_path.stem}.scan-cleanup.test.tmp.pdf")
        raw_path.write_bytes(b"raw")
        cleanup_path.write_text("{}", encoding="utf-8")
        temp_path.write_bytes(b"tmp")

        self.service._delete_source_scan_cleanup_artifacts(source_file_id)

        self.assertFalse(raw_path.exists())
        self.assertFalse(cleanup_path.exists())
        self.assertFalse(temp_path.exists())


if __name__ == "__main__":
    unittest.main()
