import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.core.errors import APIError
from app.services.documents import DocumentService


class _FakeDb:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


class DocumentMetadataSuggestionTest(unittest.TestCase):
    def test_raises_service_unavailable_when_ai_classification_fails(self) -> None:
        db = _FakeDb()
        document = SimpleNamespace(
            id=uuid.uuid4(),
            ai_status="pending",
            ocr_quality_status="good",
            ocr_confidence_score=91.0,
        )
        service = DocumentService(db)
        captured_kwargs = {}

        def fake_classification(doc, **_kwargs):
            captured_kwargs.update(_kwargs)
            doc.ai_status = "error"
            return "Ollama-Klassifizierung fehlgeschlagen: Netzwerk nicht erreichbar."

        with (
            patch.object(service, "get_document_or_404", return_value=document),
            patch.object(service, "_extract_text_for_manual_auto_tagging", return_value="OCR Text"),
            patch(
                "app.services.documents.SettingsService",
                return_value=SimpleNamespace(
                    get_settings=lambda: SimpleNamespace(
                        model_dump=lambda mode="json": {
                            "ollama": {
                                "enabled": True,
                                "base_url": "http://ollama.test:11434",
                                "model": "test-model",
                                "timeout_seconds": 12.5,
                            }
                        }
                    )
                ),
            ),
            patch("app.services.documents.load_active_document_type_vocab", return_value=[]),
            patch("app.services.documents.apply_ollama_classification", side_effect=fake_classification),
        ):
            with self.assertRaises(APIError) as raised:
                service.suggest_metadata(document.id)

        self.assertTrue(db.committed)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.code, "AI_METADATA_UNAVAILABLE")
        self.assertIn("Ollama-Klassifizierung fehlgeschlagen", raised.exception.message)
        self.assertEqual(captured_kwargs["base_url"], "http://ollama.test:11434")
        self.assertEqual(captured_kwargs["model"], "test-model")
        self.assertEqual(captured_kwargs["timeout_seconds"], 12.5)

    def test_raises_conflict_when_no_ocr_text_is_available(self) -> None:
        db = _FakeDb()
        document = SimpleNamespace(id=uuid.uuid4(), ai_status="pending")
        service = DocumentService(db)

        with (
            patch.object(service, "get_document_or_404", return_value=document),
            patch.object(service, "_extract_text_for_manual_auto_tagging", return_value=""),
        ):
            with self.assertRaises(APIError) as raised:
                service.suggest_metadata(document.id)

        self.assertFalse(db.committed)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.code, "AI_METADATA_NO_TEXT")

    def test_returns_matched_correspondent_from_ai_sender(self) -> None:
        db = _FakeDb()
        correspondent_id = uuid.uuid4()
        document = SimpleNamespace(
            id=uuid.uuid4(),
            ai_status="done",
            ai_sender="HUK-COBURG, HUK-COBURG VVaG",
            ai_document_date=None,
            ai_summary="",
            ai_suggested_tags=[],
            display_name=None,
            original_filename="Beitragsrechnung Kfz-Versicherung Januar 2024.pdf",
        )
        service = DocumentService(db)
        fake_match = SimpleNamespace(correspondent_id=correspondent_id, name="HUK-Coburg")
        fake_resolver = SimpleNamespace(resolve=lambda **kwargs: fake_match)

        with (
            patch.object(service, "get_document_or_404", return_value=document),
            patch.object(service, "_extract_text_for_manual_auto_tagging", return_value="HUK-COBURG VVaG"),
            patch.object(service, "_build_ai_title", return_value=None),
            patch.object(service, "_suggest_document_type_from_classification", return_value=None),
            patch.object(service, "_suggest_tags_from_classification", return_value=[]),
            patch("app.services.documents.CorrespondentMatchingService", return_value=fake_resolver),
        ):
            suggestion = service.suggest_metadata(document.id)

        self.assertEqual(suggestion.correspondent_id, correspondent_id)
        self.assertEqual(suggestion.correspondent_name, "HUK-Coburg")


if __name__ == "__main__":
    unittest.main()
