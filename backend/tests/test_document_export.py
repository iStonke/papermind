"""Tests für den ZIP-Export der Auswahl (``DocumentService.build_export_archive``).

Zwei Ebenen:
- Reine Logik ohne DB: Rollenwahl (OCR bevorzugt, Original-Fallback) und die
  eindeutige, sichere Dateibenennung im Archiv.
- Integration gegen die echte DB (wie ``test_rls_isolation``): Zusammenbau des
  ZIP, Überspringen von Metadaten-only-Dokumenten und Owner-Isolation. Wird
  übersprungen, wenn keine App-DB erreichbar ist.
"""

import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models.document_file import DocumentFile
from app.schemas.documents import DocumentFileRole
from app.services.documents import DocumentService


class ExportNamingAndSelectionTest(unittest.TestCase):
    """Reine Logik – kein DB-Zugriff nötig."""

    def setUp(self) -> None:
        self.service = DocumentService(None)

    @staticmethod
    def _file(role: str, filename: str) -> DocumentFile:
        return DocumentFile(
            document_id=uuid.uuid4(),
            role=role,
            file_key=f"key/{filename}",
            filename=filename,
            mime_type="application/pdf",
        )

    def test_prefers_ocr_over_original(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key=None,
            mime_type="application/pdf",
            files=[self._file("original", "original.pdf"), self._file("ocr", "ocr.pdf")],
        )
        chosen = self.service._select_exportable_file(document)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.role, DocumentFileRole.ocr.value)

    def test_falls_back_to_original_when_no_ocr(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key=None,
            mime_type="application/pdf",
            files=[self._file("original", "original.pdf")],
        )
        chosen = self.service._select_exportable_file(document)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.role, DocumentFileRole.original.value)

    def test_uses_legacy_storage_key_when_no_file_rows(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key="abc/original.pdf",
            mime_type="application/pdf",
            files=[],
        )
        chosen = self.service._select_exportable_file(document)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.role, DocumentFileRole.original.value)
        self.assertEqual(chosen.file_key, "abc/original.pdf")

    def test_metadata_only_document_has_no_exportable_file(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key=None,
            mime_type="application/pdf",
            files=[],
        )
        self.assertIsNone(self.service._select_exportable_file(document))

    def test_searchable_role_prefers_ocr(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key=None,
            mime_type="application/pdf",
            files=[self._file("original", "original.pdf"), self._file("ocr", "ocr.pdf")],
        )
        record = self.service._get_file_record_by_role(document, DocumentFileRole.searchable)
        self.assertEqual(record.role, DocumentFileRole.ocr.value)

    def test_searchable_role_falls_back_to_original(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key=None,
            mime_type="application/pdf",
            files=[self._file("original", "original.pdf")],
        )
        record = self.service._get_file_record_by_role(document, DocumentFileRole.searchable)
        self.assertEqual(record.role, DocumentFileRole.original.value)

    def test_searchable_role_raises_when_no_file(self) -> None:
        document = SimpleNamespace(
            id=uuid.uuid4(),
            original_filename="beleg.pdf",
            storage_key=None,
            mime_type="application/pdf",
            files=[],
        )
        from app.core.errors import NotFoundError
        with self.assertRaises(NotFoundError):
            self.service._get_file_record_by_role(document, DocumentFileRole.searchable)

    def test_unique_name_forces_pdf_and_resolves_collisions(self) -> None:
        used: set[str] = set()
        doc = SimpleNamespace(original_filename="Rechnung 2024.pdf")
        first = DocumentService._unique_export_name(doc, used)
        second = DocumentService._unique_export_name(doc, used)
        self.assertEqual(first, "Rechnung 2024.pdf")
        self.assertEqual(second, "Rechnung 2024 (2).pdf")

    def test_unique_name_sanitizes_invalid_characters(self) -> None:
        used: set[str] = set()
        doc = SimpleNamespace(original_filename="Ordner/Datei:*name")
        name = DocumentService._unique_export_name(doc, used)
        self.assertTrue(name.endswith(".pdf"))
        for forbidden in '/\\:*?"<>|':
            self.assertNotIn(forbidden, name)

    def test_unique_name_falls_back_when_empty(self) -> None:
        used: set[str] = set()
        doc = SimpleNamespace(original_filename="")
        self.assertEqual(DocumentService._unique_export_name(doc, used), "Dokument.pdf")

    def test_empty_selection_raises(self) -> None:
        with self.assertRaises(BadRequestError):
            self.service.build_export_archive([])


_PDF_ORIGINAL = b"%PDF-1.4\nORIGINAL-CONTENT\n"
_PDF_OCR = b"%PDF-1.4\nOCR-CONTENT\n"


def _make_user(db, suffix: str):
    from app.models.user import User

    user = User(
        username=f"export-test-{suffix}-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_doc(db, owner_id: uuid.UUID, filename: str):
    from app.models.document import Document

    doc = Document(
        owner_id=owner_id,
        original_filename=filename,
        status="imported",
        ocr_status="not_started",
        text_source="none",
        is_unread=True,
    )
    db.add(doc)
    db.flush()
    return doc


class BuildExportArchiveIntegrationTest(unittest.TestCase):
    """Baut echte ZIPs aus auf Platte liegenden PDFs und prüft die DB-Auswahl."""

    @classmethod
    def setUpClass(cls) -> None:
        from app.db.session import SessionLocal, app_engine
        from sqlalchemy import text

        try:
            with app_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"App-DB nicht erreichbar: {exc}")

        cls.storage_root = Path(get_settings().storage_path).resolve()
        cls.written_paths: list[Path] = []
        cls.db = SessionLocal()  # Superuser (umgeht RLS) für Setup/Teardown

        cls.user_a = _make_user(cls.db, "a")
        cls.user_b = _make_user(cls.db, "b")
        cls.db.commit()

        # doc_ocr: Original + OCR → OCR muss gewählt werden.
        cls.doc_ocr = _make_doc(cls.db, cls.user_a.id, "Rechnung OCR.pdf")
        cls._add_file(cls.doc_ocr, "original", "original.pdf", _PDF_ORIGINAL)
        cls._add_file(cls.doc_ocr, "ocr", "ocr.pdf", _PDF_OCR)

        # doc_original: nur Original.
        cls.doc_original = _make_doc(cls.db, cls.user_a.id, "Nur Original.pdf")
        cls._add_file(cls.doc_original, "original", "original.pdf", _PDF_ORIGINAL)

        # doc_meta: reine Metadaten, keine Datei → wird übersprungen.
        cls.doc_meta = _make_doc(cls.db, cls.user_a.id, "Nur Metadaten.pdf")

        # Zwei Dokumente mit identischem Namen → Kollisionsauflösung.
        cls.doc_dup1 = _make_doc(cls.db, cls.user_a.id, "Beleg.pdf")
        cls._add_file(cls.doc_dup1, "original", "original.pdf", _PDF_ORIGINAL)
        cls.doc_dup2 = _make_doc(cls.db, cls.user_a.id, "Beleg.pdf")
        cls._add_file(cls.doc_dup2, "original", "original.pdf", _PDF_ORIGINAL)

        # Fremdes Dokument (user_b) → darf im Export von user_a nie auftauchen.
        cls.doc_foreign = _make_doc(cls.db, cls.user_b.id, "Fremd.pdf")
        cls._add_file(cls.doc_foreign, "original", "original.pdf", _PDF_ORIGINAL)

        cls.db.commit()
        cls.service = DocumentService(cls.db, cls.user_a.id)

    @classmethod
    def _add_file(cls, document, role: str, filename: str, content: bytes) -> None:
        key = f"{document.id}/{filename}"
        path = cls.storage_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        cls.written_paths.append(path)
        cls.db.add(
            DocumentFile(
                document_id=document.id,
                role=role,
                file_key=key,
                filename=filename,
                mime_type="application/pdf",
                bytes=len(content),
            )
        )
        cls.db.flush()

    @classmethod
    def tearDownClass(cls) -> None:
        from sqlalchemy import text

        for uid in (getattr(cls, "user_a", None), getattr(cls, "user_b", None)):
            if uid is not None:
                cls.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid.id})
        cls.db.commit()
        cls.db.close()
        for path in getattr(cls, "written_paths", []):
            try:
                path.unlink(missing_ok=True)
                if path.parent.exists() and not any(path.parent.iterdir()):
                    path.parent.rmdir()
            except OSError:
                pass

    def test_prefers_ocr_and_skips_metadata_only(self) -> None:
        tmp_path, name, skipped = self.service.build_export_archive(
            [self.doc_ocr.id, self.doc_original.id, self.doc_meta.id]
        )
        try:
            self.assertEqual(skipped, 1)  # doc_meta übersprungen
            self.assertTrue(name.startswith("papermind-export-"))
            with zipfile.ZipFile(tmp_path) as archive:
                names = set(archive.namelist())
                self.assertEqual(names, {"Rechnung OCR.pdf", "Nur Original.pdf"})
                # OCR-Fassung wurde für doc_ocr gewählt (nicht das Original).
                self.assertEqual(archive.read("Rechnung OCR.pdf"), _PDF_OCR)
                self.assertEqual(archive.read("Nur Original.pdf"), _PDF_ORIGINAL)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_deduplicates_colliding_names(self) -> None:
        tmp_path, _name, skipped = self.service.build_export_archive(
            [self.doc_dup1.id, self.doc_dup2.id]
        )
        try:
            self.assertEqual(skipped, 0)
            with zipfile.ZipFile(tmp_path) as archive:
                self.assertEqual(set(archive.namelist()), {"Beleg.pdf", "Beleg (2).pdf"})
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_excludes_foreign_owner_document(self) -> None:
        tmp_path, _name, skipped = self.service.build_export_archive(
            [self.doc_original.id, self.doc_foreign.id]
        )
        try:
            self.assertEqual(skipped, 1)  # fremdes Dokument herausgefiltert
            with zipfile.ZipFile(tmp_path) as archive:
                self.assertEqual(set(archive.namelist()), {"Nur Original.pdf"})
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_only_metadata_selection_raises(self) -> None:
        with self.assertRaises(BadRequestError):
            self.service.build_export_archive([self.doc_meta.id])


if __name__ == "__main__":
    unittest.main()
