"""Tests für das Umsortieren von PDF-Seiten.

Zwei Ebenen ohne DB-Zugriff:
- ``DocumentStorageService.reorder_pdf_pages`` schreibt die Seiten in neuer
  Reihenfolge und lehnt ungültige Permutationen ab. Die Seitenidentität wird
  über unterschiedliche Seitenbreiten geprüft (kein Text-Rendering nötig).
- ``PageReorderRequest`` validiert, dass ``order`` eine echte Permutation ist.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pydantic
from pypdf import PdfReader, PdfWriter

from app.core.errors import BadRequestError
from app.schemas.documents import PageReorderRequest
from app.services.document_storage import DocumentStorageService


def _write_marked_pdf(path: Path, widths: list[float]) -> None:
    """Erzeugt ein PDF, dessen Seiten sich an ihrer Breite unterscheiden lassen."""
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=200)
    with path.open("wb") as handle:
        writer.write(handle)


def _page_widths(path: Path) -> list[float]:
    reader = PdfReader(str(path))
    return [round(float(page.mediabox.width)) for page in reader.pages]


class ReorderPdfPagesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pdf_path = Path(self._tmp.name) / "doc.pdf"
        # Vier Seiten mit klar unterscheidbaren Breiten 100/200/300/400.
        _write_marked_pdf(self.pdf_path, [100, 200, 300, 400])

    def test_reorders_pages_in_place(self) -> None:
        # Neue Reihenfolge: alte Seiten 3,1,4,2 → Breiten 300,100,400,200.
        new_size = DocumentStorageService.reorder_pdf_pages(self.pdf_path, [3, 1, 4, 2])
        self.assertEqual(_page_widths(self.pdf_path), [300, 100, 400, 200])
        self.assertEqual(new_size, self.pdf_path.stat().st_size)
        self.assertGreater(new_size, 0)

    def test_identity_order_keeps_pages(self) -> None:
        DocumentStorageService.reorder_pdf_pages(self.pdf_path, [1, 2, 3, 4])
        self.assertEqual(_page_widths(self.pdf_path), [100, 200, 300, 400])

    def test_rejects_wrong_length(self) -> None:
        with self.assertRaises(BadRequestError):
            DocumentStorageService.reorder_pdf_pages(self.pdf_path, [1, 2, 3])

    def test_rejects_non_permutation(self) -> None:
        with self.assertRaises(BadRequestError):
            DocumentStorageService.reorder_pdf_pages(self.pdf_path, [1, 2, 3, 3])

    def test_no_temp_file_left_behind(self) -> None:
        DocumentStorageService.reorder_pdf_pages(self.pdf_path, [4, 3, 2, 1])
        leftovers = list(self.pdf_path.parent.glob("*.reordering"))
        self.assertEqual(leftovers, [])


class PageReorderRequestValidationTest(unittest.TestCase):
    def test_accepts_valid_permutation(self) -> None:
        self.assertEqual(PageReorderRequest(order=[3, 1, 2]).order, [3, 1, 2])

    def test_rejects_duplicate_pages(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            PageReorderRequest(order=[1, 1, 2])

    def test_rejects_gap_in_pages(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            PageReorderRequest(order=[1, 2, 4])

    def test_rejects_empty(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            PageReorderRequest(order=[])


if __name__ == "__main__":
    unittest.main()
