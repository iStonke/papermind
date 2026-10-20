import json
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from app.services import import_staging
from app.services.import_staging import ImportStagingService


class ImportAnalysisJobsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.storage = patch.object(import_staging.settings, "storage_path", self.directory.name)
        self.storage.start()
        self.addCleanup(self.storage.stop)
        self.service = self.service_instance()
        self.source_id = str(uuid.uuid4())
        self.path = self.service._source_pdf_path(self.source_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"synthetic source")

    def service_instance(self):
        service = ImportStagingService(None)
        service._analysis_recipe = lambda: "test-recipe"
        return service

    def test_live_snapshot_fills_early_and_duplicate_post_joins_the_running_job(self):
        early = threading.Event()
        finish = threading.Event()
        self.addCleanup(finish.set)
        def analyze(*args, **kwargs):
            self.service._publish_analysis_progress({"status": "ready", "suggestion": "Brief", "meta": {"date": "2026-10-15", "analysis_phase": "rule"}})
            early.set()
            finish.wait(5)
            return {"status": "ready", "suggestion": "Brief vom Arbeitgeber", "meta": {"analysis_phase": "llm"}}
        self.service._suggest_stage_title = Mock(side_effect=analyze)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.service.suggest_stage_title, [self.source_id], stage_id="stage", document_revision="revision")
            self.assertTrue(early.wait(3))
            reader = self.service_instance()
            progress = reader.get_stage_analysis("stage", "revision", [self.source_id])
            self.assertEqual(progress["meta"]["date"], "2026-10-15")
            self.assertTrue(progress["meta"]["analysis_pending"])
            reader._suggest_stage_title = Mock(side_effect=AssertionError("duplicate expensive work"))
            joined = reader.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision", force=True)
            self.assertEqual(joined["meta"]["analysis_job_id"], progress["meta"]["analysis_job_id"])
            finish.set()
            result = future.result(3)
        self.assertFalse(result["meta"]["analysis_pending"])
        self.assertGreater(result["meta"]["analysis_sequence"], progress["meta"]["analysis_sequence"])
        self.assertEqual(reader.get_stage_analysis("stage", "revision", [self.source_id])["suggestion"], "Brief vom Arbeitgeber")
        self.service._suggest_stage_title.assert_called_once()

    def test_failed_refinement_keeps_the_early_fields_in_the_server_snapshot(self):
        def analyze(*args, **kwargs):
            self.service._publish_analysis_progress({"status": "ready", "suggestion": "Brief", "meta": {"date": "2026-10-15", "analysis_phase": "rule"}})
            raise RuntimeError("synthetic model failure")
        self.service._suggest_stage_title = analyze
        with self.assertRaises(RuntimeError):
            self.service.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision")
        result = self.service.get_stage_analysis("stage", "revision", [self.source_id])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["meta"]["date"], "2026-10-15")
        self.assertFalse(result["meta"]["analysis_pending"])
        self.assertTrue(result["meta"]["refinement_failed"])

    def test_selected_pages_publish_the_rule_result_before_calling_the_model(self):
        from pypdf import PdfWriter
        from app.schemas.import_staging import ImportCommitPageInput
        selected = self.path.parent / "selected.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=280)
        with selected.open("wb") as stream:
            writer.write(stream)
        self.service._build_document_pdf = Mock(return_value=(selected, 1))
        def build(**kwargs):
            if kwargs["use_ollama"]:
                snapshot = self.service_instance().get_stage_analysis("stage", "revision", [self.source_id])
                self.assertEqual(snapshot["meta"]["date"], "2026-10-15")
                self.assertTrue(snapshot["meta"]["analysis_pending"])
            return {"status": "ready", "suggestion": "Brief", "meta": {"date": "2026-10-15",
                "analysis_phase": "llm" if kwargs["use_ollama"] else "rule"}}
        self.service._build_stage_title_result = Mock(side_effect=build)
        with patch.object(import_staging, "run_ocr_lite", return_value="Ein ausreichend langer synthetischer Brief mit lesbarem Text zur Analyse des Dokuments. " * 3):
            result = self.service.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision",
                pages=[ImportCommitPageInput(source_file_id=self.source_id, page_index=0)])
        self.assertFalse(result["meta"]["analysis_pending"])
        self.assertEqual([call.kwargs["use_ollama"] for call in self.service._build_stage_title_result.call_args_list], [False, True])

    def test_status_read_checks_source_authorization(self):
        denied = self.service_instance()
        denied.get_source_pdf_path = Mock(side_effect=import_staging.ForbiddenError("synthetic forbidden source"))
        with self.assertRaises(import_staging.ForbiddenError):
            denied.get_stage_analysis("stage", "revision", [self.source_id])
        denied.get_source_pdf_path.assert_called_once_with(self.source_id)

    def test_worker_completion_clears_a_rule_results_refinement_flag(self):
        cached = {"status": "ready", "suggestion": "Brief", "meta": {"analysis_phase": "rule", "refinement_pending": True}}
        self.service.get_source_analysis = Mock(return_value=cached)
        self.service.mark_source_preanalysis_pending([self.source_id])
        waiting = self.service.get_source_analysis_response(self.source_id)
        self.assertTrue(waiting["meta"]["analysis_pending"])
        self.assertTrue(waiting["meta"]["refinement_pending"])
        self.service.clear_source_preanalysis_pending(self.source_id)
        completed = self.service.get_source_analysis_response(self.source_id)
        self.assertFalse(completed["meta"]["analysis_pending"])
        self.assertFalse(completed["meta"]["refinement_pending"])
        self.assertTrue(cached["meta"]["refinement_pending"])

    def test_force_joins_worker_even_with_explicit_original_page(self):
        from app.schemas.import_staging import ImportCommitPageInput
        self.service.mark_source_preanalysis_pending([self.source_id])
        self.service.get_source_analysis = Mock(return_value=None)
        self.service._suggest_stage_title = Mock(side_effect=AssertionError("duplicate OCR"))
        result = self.service.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision", force=True,
            pages=[ImportCommitPageInput(source_file_id=self.source_id, page_index=0)])
        self.assertTrue(result["meta"]["analysis_pending"])
        self.service._suggest_stage_title.assert_not_called()

    def test_snapshots_are_isolated_by_revision_source_version_and_owner(self):
        self.service._suggest_stage_title = Mock(return_value={"status": "ready", "suggestion": "Brief", "meta": {}})
        self.service.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision")
        self.assertEqual(self.service.get_stage_analysis("stage", "other-revision", [self.source_id])["status"], "unknown")
        other = self.service_instance()
        other.owner_id = uuid.uuid4()
        other._authorized_sources.add(self.source_id)
        self.assertEqual(other.get_stage_analysis("stage", "revision", [self.source_id])["status"], "unknown")
        self.path.write_bytes(b"new source bytes")
        self.assertEqual(self.service.get_stage_analysis("stage", "revision", [self.source_id])["status"], "unknown")

    def test_completed_analysis_can_be_read_without_starting_work_and_expires(self):
        self.service._suggest_stage_title = Mock(return_value={"status": "ready", "suggestion": "Brief", "meta": {}})
        self.service.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision")
        self.service.suggest_stage_title([self.source_id], stage_id="stage", document_revision="revision")
        self.service._suggest_stage_title.assert_called_once()
        job = self.service._stage_analysis_job("stage", "revision", [self.source_id])
        snapshot = job.read()
        snapshot["updated_at"] = 0
        job.path.write_text(json.dumps(snapshot))
        self.assertEqual(self.service.get_stage_analysis("stage", "revision", [self.source_id])["status"], "unknown")
