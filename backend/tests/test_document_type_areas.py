import unittest

from pydantic import ValidationError

from app.schemas.document_types import DocumentTypeCreateRequest, DocumentTypeUpdateRequest


class DocumentTypeAreaSchemaTests(unittest.TestCase):
    def test_create_accepts_supported_area(self) -> None:
        payload = DocumentTypeCreateRequest(name="Rechnung", area="finance")
        self.assertEqual(payload.area, "finance")

    def test_update_allows_clearing_area(self) -> None:
        payload = DocumentTypeUpdateRequest.model_validate({"area": None})
        self.assertIn("area", payload.model_fields_set)
        self.assertIsNone(payload.area)

    def test_rejects_unknown_area(self) -> None:
        with self.assertRaises(ValidationError):
            DocumentTypeUpdateRequest(area="shopping")


if __name__ == "__main__":
    unittest.main()
