import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.document_wiki import render_document_wiki_entry


class DocumentWikiTest(unittest.TestCase):
    def test_compiled_entry_keeps_metadata_and_marks_it_as_derived(self) -> None:
        document = SimpleNamespace(
            display_name="Stromrechnung Juli",
            original_filename="strom.pdf",
            document_type="Rechnung",
            ai_document_type=None,
            document_date=date(2026, 7, 1),
            ai_document_date=None,
            ai_sender="Stadtwerke",
            ai_recipient="Max Mustermann",
            ai_amount=Decimal("42.50"),
            ai_currency="EUR",
            ai_summary="Abschlagsrechnung für Strom im Juli.",
        )

        content = render_document_wiki_entry(document)

        self.assertIn("# Stromrechnung Juli", content)
        self.assertIn("42,50 EUR", content)
        self.assertIn("Automatisch verdichtete Arbeitsnotiz", content)
        self.assertIn("Originaldokument", content)


if __name__ == "__main__":
    unittest.main()
