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
    def test_legacy_fallback_matches_previous_schema(self) -> None:
        meta = {
            "doc_type": "Rechnung",
            "issuer": "Vodafone GmbH",
            "subject": "Mobilfunk Januar 2024",
            "amount": 42.5,
        }

        self.assertEqual(
            NamingTemplateService().build_filename(meta),
            "Rechnung – Vodafone GMBH – Mobilfunk Januar 2024 – 42,50€",
        )
        self.assertEqual(NamingTemplateService().build_filename(meta), build_legacy_filename_from_meta(meta))

    def test_global_template_renders_exact_golden_sample(self) -> None:
        service = NamingTemplateService(
            _TemplateDb("Rechnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy} – {betrag}")
        )
        meta = {
            "doc_type": "Rechnung",
            "document_type": "Rechnung",
            "issuer": "HUK-Coburg",
            "correspondent": {"name": "HUK-Coburg", "short_name": "HUK"},
            "subject": "Kfz-Versicherung Januar 2024",
            "date": "2024-01-01",
            "amount": 87.3,
        }

        self.assertEqual(
            service.build_filename(meta),
            "Rechnung – HUK – Kfz-Versicherung Januar 2024 – 01.01.2024 – 87,30€",
        )

    def test_missing_required_placeholder_stays_visible(self) -> None:
        service = NamingTemplateService(_TemplateDb("Beitragsrechnung – {korrespondent} – {sparte} – {monat} {jahr}"))
        meta = {
            "doc_type": "Beitragsrechnung",
            "document_type": "Beitragsrechnung",
            "correspondent": {"name": "HUK-Coburg", "short_name": "HUK"},
            "date": "2024-01-01",
        }

        self.assertEqual(
            service.build_filename(meta),
            "Beitragsrechnung – HUK – {sparte} – 1 2024",
        )

    def test_empty_template_uses_fallback(self) -> None:
        meta = {"doc_type": "Brief", "issuer": "", "subject": ""}

        self.assertEqual(
            NamingTemplateService(_TemplateDb("")).build_filename(meta),
            "Brief – Unbekannt – Ohne Betreff",
        )


if __name__ == "__main__":
    unittest.main()
