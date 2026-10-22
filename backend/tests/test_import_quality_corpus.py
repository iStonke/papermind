import json
import unittest
from scripts.evaluate_import_corpus import CORPUS, evaluate, rule_prediction


class ImportQualityCorpusTest(unittest.TestCase):
    def test_metadata_fields_on_representative_synthetic_ocr_corpus(self):
        cases = json.loads(CORPUS.read_text())["cases"]
        self.assertTrue({"letter", "invoice", "handwriting-transcript", "degraded-ocr", "multipage"}.issubset({case["kind"] for case in cases}))
        report = evaluate(cases, rule_prediction)
        self.assertEqual(report["failures"], [], json.dumps(report, ensure_ascii=False, indent=2))

    def test_metrics_detect_hallucinations_missing_fields_and_wrong_values(self):
        cases = [{"id": "probe", "expected": {"title": None, "date": "2026-10-15", "note": {"contains": "Mitgliedschaft"}}}]
        report = evaluate(cases, lambda _: {"title": "Ohne Betreff", "date": "2026-10-31", "note": ""})
        self.assertEqual(report["fields"]["title"]["false_positive"], 1)
        self.assertEqual(report["fields"]["note"]["missing"], 1)
        self.assertEqual(len(report["failures"]), 3)
