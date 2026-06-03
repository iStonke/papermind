import unittest

from app.services.naming_templates import NamingTemplateService, build_legacy_filename_from_meta


class _ScalarResult:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> str | None:
        return self.value


class _TemplateDb:
    def __init__(self, template: str | None) -> None:
        self.template = template

    def execute(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self.template)


class NamingTemplateServiceTest(unittest.TestCase):
    def test_legacy_fallback_subject_first_no_type(self) -> None:
        # Hausschema: Betreff zuerst, kein Dokumenttyp, Leerzeichen-getrennt.
        meta = {
            "doc_type": "Rechnung",
            "issuer": "Vodafone GmbH",
            "subject": "Mobilfunk Januar 2024",
            "amount": 42.5,
        }

        self.assertEqual(
            NamingTemplateService().build_filename(meta),
            "Mobilfunk Januar 2024 Vodafone GMBH 42,50€",
        )
        self.assertEqual(NamingTemplateService().build_filename(meta), build_legacy_filename_from_meta(meta))

    def test_global_template_renders_betreff_and_date(self) -> None:
        service = NamingTemplateService(_TemplateDb("{betreff} {datum:dd.MM.yyyy}"))
        meta = {
            "document_type": "Rechnung",
            "subject": "Wiker Auto-Service Bremsen",
            "date": "2013-09-30",
        }

        self.assertEqual(service.build_filename(meta), "Wiker Auto-Service Bremsen 30.09.2013")

    def test_month_placeholder_renders_german_name(self) -> None:
        service = NamingTemplateService(_TemplateDb("{betreff} {monat} {jahr}"))
        meta = {
            "document_type": "Beitragsrechnung",
            "subject": "Kfz-Versicherung",
            "date": "2024-01-01",
        }

        self.assertEqual(service.build_filename(meta), "Kfz-Versicherung Januar 2024")

    def test_missing_placeholder_is_dropped(self) -> None:
        # Fehlendes Datum wird weggelassen – kein sichtbares {platzhalter}.
        service = NamingTemplateService(_TemplateDb("{betreff} {datum:dd.MM.yyyy}"))
        meta = {"document_type": "Kündigung", "subject": "Mitgliedschaftskündigung"}

        self.assertEqual(service.build_filename(meta), "Mitgliedschaftskündigung")

    def test_duplicate_year_is_collapsed(self) -> None:
        # KI packt Jahr bereits in den Betreff, Template hängt {jahr} an -> nur einmal.
        service = NamingTemplateService(_TemplateDb("{betreff} {jahr}"))
        meta = {"document_type": "Steuerbescheid", "subject": "Einkommensteuer 2024", "date": "2024-02-12"}

        self.assertEqual(service.build_filename(meta), "Einkommensteuer 2024")

    def test_empty_template_uses_fallback(self) -> None:
        meta = {"doc_type": "Brief", "issuer": "", "subject": ""}

        self.assertEqual(NamingTemplateService(_TemplateDb("")).build_filename(meta), "Dokument")


if __name__ == "__main__":
    unittest.main()
