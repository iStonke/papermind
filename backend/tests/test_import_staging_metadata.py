import unittest
from unittest.mock import Mock

from app.services.import_staging import ImportStagingService


class ImportStagingMetadataTest(unittest.TestCase):
    def test_returns_worker_rule_cache_without_starting_duplicate_analysis(self) -> None:
        service = object.__new__(ImportStagingService)
        cached = {"status": "ready", "suggestion": "NDR – Absage", "meta": {"analysis_phase": "rule"}}
        service.get_source_analysis = Mock(return_value=cached)
        service.is_source_preanalysis_pending = Mock(return_value=True)
        service._extract_text_for_title_suggestion = Mock()

        result = service.suggest_stage_title(["a1d5d29e-1d54-4c28-908b-87561a4812d3"], stage_id="stage-1")

        self.assertIs(result, cached)
        service._extract_text_for_title_suggestion.assert_not_called()

    def test_reports_pending_while_worker_preanalysis_owns_source(self) -> None:
        service = object.__new__(ImportStagingService)
        service.get_source_analysis = Mock(return_value=None)
        service.is_source_preanalysis_pending = Mock(return_value=True)
        service._extract_text_for_title_suggestion = Mock()

        result = service.suggest_stage_title(["a1d5d29e-1d54-4c28-908b-87561a4812d3"], stage_id="stage-1")

        self.assertEqual(result["status"], "pending_ocr")
        self.assertEqual(result["meta"]["analysis_phase"], "worker_queue")
        service._extract_text_for_title_suggestion.assert_not_called()

    def test_coerce_llm_scalar_extracts_text_objects(self) -> None:
        self.assertEqual(
            ImportStagingService._coerce_llm_scalar({"text": "Finanzamt Kiel"}),
            "Finanzamt Kiel",
        )
        self.assertEqual(
            ImportStagingService._coerce_llm_scalar({"value": {"text": "Bescheid über Einkommensteuer"}}),
            "Bescheid über Einkommensteuer",
        )

    def test_coerce_llm_scalar_ignores_empty_objects(self) -> None:
        self.assertIsNone(ImportStagingService._coerce_llm_scalar({"confidence": 0.8}))
        self.assertIsNone(ImportStagingService._coerce_llm_scalar(["", {"text": "  "}]))

    def test_coerce_llm_scalar_supports_list_fallback(self) -> None:
        self.assertEqual(
            ImportStagingService._coerce_llm_scalar([{"confidence": 0.5}, {"text": "Steuer"}]),
            "Steuer",
        )


if __name__ == "__main__":
    unittest.main()
