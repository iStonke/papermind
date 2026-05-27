import unittest

from app.services.ocr_pipeline import _build_quality_metrics, _normalize_tesseract_languages, _postprocess_hyphenation


class OCRPipelineTest(unittest.TestCase):
    def test_language_normalization_defaults_to_german_and_english(self) -> None:
        self.assertEqual(_normalize_tesseract_languages(""), "deu+eng")
        self.assertEqual(_normalize_tesseract_languages("deu, eng deu"), "deu+eng")

    def test_hyphenation_postprocessing_joins_line_end_words(self) -> None:
        self.assertEqual(_postprocess_hyphenation("Ver-\narbeitung"), "Verarbeitung")

    def test_quality_thresholds(self) -> None:
        good = _build_quality_metrics("Das ist ein lesbarer OCR Text mit ausreichend Inhalt.", [0.81], [])
        warning = _build_quality_metrics("Das ist ein lesbarer OCR Text mit ausreichend Inhalt.", [0.79], [])
        error = _build_quality_metrics("Das ist ein lesbarer OCR Text mit ausreichend Inhalt.", [0.59], [])

        self.assertEqual(good["status"], "good")
        self.assertEqual(warning["status"], "warning")
        self.assertEqual(error["status"], "error")
        self.assertEqual(good["confidence_score"], 81.0)


if __name__ == "__main__":
    unittest.main()
