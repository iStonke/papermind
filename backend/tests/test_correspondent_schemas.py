import unittest
import uuid

from pydantic import ValidationError

from app.schemas.correspondents import (
    CorrespondentAliasCreateRequest,
    CorrespondentCreateRequest,
    CorrespondentUpdateRequest,
)
from app.schemas.import_staging import ImportCommitDocumentInput


class CorrespondentSchemaTest(unittest.TestCase):
    def test_create_normalizes_name_whitespace(self) -> None:
        payload = CorrespondentCreateRequest(name="  Vodafone   GmbH  ")
        self.assertEqual(payload.name, "Vodafone GmbH")

    def test_create_allows_long_names(self) -> None:
        # Korrespondentennamen dürfen länger als das 30-Zeichen-Vokabular sein.
        long_name = "Kassenärztliche Vereinigung Schleswig-Holstein"
        payload = CorrespondentCreateRequest(name=long_name)
        self.assertEqual(payload.name, long_name)

    def test_create_rejects_too_short_name(self) -> None:
        with self.assertRaises(ValidationError):
            CorrespondentCreateRequest(name="A")

    def test_create_normalizes_optional_text_to_none(self) -> None:
        payload = CorrespondentCreateRequest(name="HUK-Coburg", short_name="   ", notes="")
        self.assertIsNone(payload.short_name)
        self.assertIsNone(payload.notes)

    def test_alias_normalizes_and_rejects_empty(self) -> None:
        payload = CorrespondentAliasCreateRequest(alias="  Red   Plus ")
        self.assertEqual(payload.alias, "Red Plus")
        with self.assertRaises(ValidationError):
            CorrespondentAliasCreateRequest(alias="   ")

    def test_kind_defaults_none_and_normalizes(self) -> None:
        self.assertIsNone(CorrespondentCreateRequest(name="Werkstatt").kind)
        self.assertEqual(CorrespondentCreateRequest(name="Werkstatt", kind=" Organization ").kind, "organization")
        self.assertEqual(CorrespondentCreateRequest(name="Torge", kind="PERSON").kind, "person")
        self.assertEqual(CorrespondentCreateRequest(name="Banken", kind=" Collection ").kind, "collection")

    def test_kind_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValidationError):
            CorrespondentCreateRequest(name="Werkstatt", kind="company")

    def test_update_accepts_kind_and_parent_id(self) -> None:
        parent = uuid.uuid4()
        payload = CorrespondentUpdateRequest(kind="person", parent_id=parent)
        self.assertEqual(payload.kind, "person")
        self.assertEqual(payload.parent_id, parent)


class ImportCommitCorrespondentTest(unittest.TestCase):
    def test_commit_document_accepts_correspondent_id(self) -> None:
        cid = uuid.uuid4()
        doc = ImportCommitDocumentInput(title="Rechnung", correspondent_id=cid)
        self.assertEqual(doc.correspondent_id, cid)

    def test_commit_document_correspondent_id_defaults_none(self) -> None:
        doc = ImportCommitDocumentInput(title="Rechnung")
        self.assertIsNone(doc.correspondent_id)


if __name__ == "__main__":
    unittest.main()
