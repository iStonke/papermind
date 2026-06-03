import unittest

from app.services.import_staging import ImportStagingService


class ImportStagingMetadataTest(unittest.TestCase):
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
