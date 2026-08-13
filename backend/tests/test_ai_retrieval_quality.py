import unittest
import uuid

from app.schemas.ai import AIRequestType
from app.services.ai import AIService
from app.services.embeddings import _build_invoice_line_chunks, _lexical_query
from app.services.wiki_search import _meaningful_terms, _text_relevance


class AIRetrievalQualityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AIService.__new__(AIService)

    def test_short_independent_question_is_not_rewritten(self) -> None:
        rewritten = AIService._rewrite_query(
            "Wie lautet die IBAN?",
            [{"role": "user", "content": "Wann endet die Mitgliedschaft?"}],
        )
        self.assertEqual(rewritten, "Wie lautet die IBAN?")

    def test_anaphoric_followup_keeps_previous_question(self) -> None:
        rewritten = AIService._rewrite_query(
            "Und wann endet das?",
            [{"role": "user", "content": "Welche Mitgliedschaft wurde gekündigt?"}],
        )
        self.assertIn("Welche Mitgliedschaft wurde gekündigt?", rewritten)
        self.assertIn("Anschlussfrage: Und wann endet das?", rewritten)

    def test_invoice_total_question_uses_labelled_total(self) -> None:
        answer = AIService._build_direct_lookup_answer(
            "Wie hoch ist die Rechnung für die Abgasanlage?",
            [
                {"score": 0.9, "text": "Abgasanlage 2,50 90,00 225,00"},
                {"score": 0.8, "text": "Gesamtbetrag EUR inkl. MwSt. 618,98"},
            ],
        )
        self.assertEqual(answer, "Der Rechnungsbetrag beträgt 618,98 €.")

    def test_compact_invoice_total_is_extracted(self) -> None:
        answer = AIService._build_direct_lookup_answer(
            "Wie hoch ist die Rechnung von Torge Quitsch?",
            [{"score": 0.9, "text": "Nummer Einzelpreis Gesamt150,00EUR 150,00"}],
        )
        self.assertEqual(answer, "Der Rechnungsbetrag beträgt 150,00 €.")

    def test_contribution_invoice_uses_current_claim_not_tax(self) -> None:
        answer = AIService._build_direct_lookup_answer(
            "Wie hoch ist die Beitragsrechnung der HUK?",
            [
                {
                    "score": 0.9,
                    "text": "Ihr Jahresbeitrag inkl. 19 % Versicherungsteuer von 66,92 € 419,10 €",
                },
                {"score": 0.8, "text": "Aktuelle Forderung von 419,10 €"},
            ],
        )
        self.assertEqual(answer, "Der Rechnungsbetrag beträgt 419,10 €.")

    def test_citation_prefers_chunk_that_contains_answer_value(self) -> None:
        doc_id = uuid.uuid4()
        citations = self.service._aggregate_citations(
            [
                {"doc_id": doc_id, "chunk_id": uuid.uuid4(), "score": 0.9, "text": "Rechnung Abgasanlage"},
                {
                    "doc_id": doc_id,
                    "chunk_id": uuid.uuid4(),
                    "score": 0.8,
                    "text": "Gesamtbetrag EUR inkl. MwSt. 618,98",
                },
            ],
            {doc_id: "Abgasanlage.pdf"},
            answer="Der Rechnungsbetrag beträgt 618,98 €.",
        )
        self.assertEqual(len(citations), 1)
        self.assertIn("618,98", citations[0]["snippet"])

    def test_citations_exclude_semantically_unrelated_documents(self) -> None:
        github_doc_id = uuid.uuid4()
        unrelated_doc_id = uuid.uuid4()
        citations = self.service._aggregate_citations(
            [
                {
                    "doc_id": github_doc_id,
                    "chunk_id": uuid.uuid4(),
                    "score": 0.8,
                    "text": "GitHub-Befehle: git status, git add, git commit und git push",
                },
                {
                    "doc_id": unrelated_doc_id,
                    "chunk_id": uuid.uuid4(),
                    "score": 0.7,
                    "text": "Hauptuntersuchung Abgasuntersuchung Prüfbericht Status bestanden",
                },
            ],
            {
                github_doc_id: "GitHub-Anleitung.txt",
                unrelated_doc_id: "HU-Bericht.pdf",
            },
            answer="Die Befehle sind git status, git add, git commit und git push.",
            question="Welche GitHub-Befehle stehen im Dokument?",
        )
        self.assertEqual([item["doc_id"] for item in citations], [github_doc_id])

    def test_citation_snippet_is_centered_on_answer_value(self) -> None:
        doc_id = uuid.uuid4()
        citations = self.service._aggregate_citations(
            [
                {
                    "doc_id": doc_id,
                    "chunk_id": uuid.uuid4(),
                    "score": 0.9,
                    "text": f"{'Versicherungsbedingungen ' * 20}Aktuelle Forderung von 419,10 €",
                },
            ],
            {doc_id: "Beitragsrechnung.pdf"},
            answer="Der Rechnungsbetrag beträgt 419,10 €.",
            question="Wie hoch ist die Beitragsrechnung?",
        )
        self.assertIn("419,10", citations[0]["snippet"])

    def test_quality_check_rejects_number_missing_from_context(self) -> None:
        flags = self.service._analyze_quality_flags(
            "Der Rechnungsbetrag beträgt 999,00 €.",
            [{"doc_id": uuid.uuid4()}],
            mode="numeric",
            repair_pass_used=False,
            context_text="Gesamtbetrag EUR inkl. MwSt. 618,98",
        )
        self.assertIs(flags["numbers_without_citations"], True)

    def test_invoice_special_chunk_keeps_total_marker_and_value(self) -> None:
        collapsed_line = (
            ("Position Menge Einzelpreis " * 20)
            + "Gesamtbetrag EUR inkl. MwSt. 618,98 "
            + ("Footer Bankverbindung " * 20)
        )
        chunks = _build_invoice_line_chunks([(1, [collapsed_line])])
        invoice_total = next(chunk for chunk in chunks if chunk["chunk_type"] == "invoice_total")
        self.assertIn("Gesamtbetrag", invoice_total["text"])
        self.assertIn("618,98", invoice_total["text"])
        self.assertLessEqual(len(invoice_total["text"]), 300)

    def test_lexical_query_is_precise_and_removes_question_words(self) -> None:
        self.assertEqual(
            _lexical_query("Wie hoch ist die Rechnung für die Abgasanlage?"),
            "rechnung abgasanlage",
        )

    def test_wiki_claim_relevance_prefers_matching_source(self) -> None:
        terms = _meaningful_terms("Wann endet die Mitgliedschaft im TSV Flintbek?")
        matching = _text_relevance(
            terms,
            "Kündigung TSV Flintbek",
            "Die Mitgliedschaft endet am 30. Juni 2026.",
        )
        unrelated = _text_relevance(terms, "Rechnung Osteopathie", "Gesamtbetrag 150,00 Euro")
        self.assertGreater(matching, unrelated)

    def test_how_high_question_is_numeric_mode(self) -> None:
        self.assertEqual(
            AIService._detect_mode("Wie hoch ist die Rechnung?", AIRequestType.answer),
            "numeric",
        )


if __name__ == "__main__":
    unittest.main()
