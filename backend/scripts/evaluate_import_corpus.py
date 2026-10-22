"""Reproducible field-level metadata evaluation; never calls a live model.

Run in the backend runtime: python scripts/evaluate_import_corpus.py
Or evaluate recorded full-pipeline/model predictions with --predictions FILE.
Prediction JSON is {case_id: {title,date,document_type,correspondent,note}}.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from app.services import import_staging
from app.services.import_staging import ImportStagingService
from app.services.import_title_formatting import build_filename_from_meta

FIELDS = ("title", "date", "document_type", "correspondent", "note")
CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/import-quality/corpus.json"


def rule_prediction(case):
    service = ImportStagingService(db=None)
    service.settings_service.get_settings = MagicMock(return_value=SimpleNamespace(model_dump=lambda **_: {"ollama": {"enabled": False}}))
    service._load_existing_tag_names = lambda: []
    # Isolate vocabulary/database availability; extraction uses the real pipeline.
    service._resolve_correspondent = lambda sender, _text: {"name": sender} if sender else None
    text = "\n\n".join(case["pages"])
    with patch.object(import_staging, "load_active_document_type_vocab", return_value=[]), patch.object(import_staging.NamingTemplateService, "build_filename", side_effect=build_filename_from_meta):
        result = service._build_stage_title_result(extracted_text=text, normalized_scope="all_pages", page_refs=[], ocr_pending=False,
                                                   ocr_diagnostics={"status": "ready"}, use_ollama=False)
    meta = result.get("meta", {})
    return {"title": (result.get("suggestion") or None) if not result.get("used_fallback") else None, "date": meta.get("date"), "document_type": meta.get("document_type"),
            "correspondent": (meta.get("correspondent") or {}).get("name"), "note": meta.get("note")}


def matches(actual, expected):
    if expected is None:
        return actual in (None, "", [], {})
    if isinstance(expected, dict):
        return str(expected["contains"]).casefold() in str(actual or "").casefold()
    return actual == expected


def evaluate(cases, predict):
    metrics = {field: {"correct": 0, "total": 0, "false_positive": 0, "missing": 0} for field in FIELDS}
    failures = []
    for case in cases:
        prediction = predict(case)
        for field, expected in case["expected"].items():
            actual = prediction.get(field)
            metric = metrics[field]
            metric["total"] += 1
            if matches(actual, expected):
                metric["correct"] += 1
            else:
                metric["false_positive"] += int(expected is None and bool(actual))
                metric["missing"] += int(expected is not None and not actual)
                failures.append({"case": case["id"], "field": field, "expected": expected, "actual": actual})
    for metric in metrics.values():
        metric["accuracy"] = round(metric["correct"] / max(1, metric["total"]), 4)
    return {"cases": len(cases), "fields": metrics, "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path)
    args = parser.parse_args()
    cases = json.loads(CORPUS.read_text())["cases"]
    recorded = json.loads(args.predictions.read_text()) if args.predictions else None
    report = evaluate(cases, (lambda case: recorded[case["id"]]) if recorded is not None else rule_prediction)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report["failures"]))
