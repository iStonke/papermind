import unittest
import uuid
from datetime import date, datetime, timezone

from pydantic import ValidationError

from app.schemas.dossiers import (
    DossierCreateRequest,
    DossierGroupCreateRequest,
    DossierGroupSummary,
    DossierItemCreateRequest,
    DossierItemPlacement,
    DossierItemRestoreWrite,
    DossierItemsDeleteRequest,
    DossierItemsRestoreRequest,
    DossierItemType,
    DossierItemUpdateRequest,
    DossierListItem,
    DossierPropertyWrite,
    DossierUpdateRequest,
)


class DossierSchemaTest(unittest.TestCase):
    def test_create_normalizes_manual_dossier_metadata(self) -> None:
        payload = DossierCreateRequest(
            title="  VW   Golf VII  ",
            dossier_type="  Fahrzeug  ",
            reference="  KI-AB   123  ",
        )

        self.assertEqual(payload.title, "VW Golf VII")
        self.assertEqual(payload.dossier_type, "Fahrzeug")
        self.assertEqual(payload.reference, "KI-AB 123")

    def test_create_rejects_inverted_dates(self) -> None:
        with self.assertRaises(ValidationError):
            DossierCreateRequest(
                title="Immobilie Musterstraße",
                opened_on=date(2026, 8, 5),
                closed_on=date(2026, 8, 4),
            )

    def test_group_title_is_normalized(self) -> None:
        payload = DossierGroupCreateRequest(title="  Wartung   und Rechnungen  ")
        self.assertEqual(payload.title, "Wartung und Rechnungen")

    def test_group_and_property_labels_reject_whitespace_only(self) -> None:
        with self.assertRaises(ValidationError):
            DossierGroupCreateRequest(title="   ")
        with self.assertRaises(ValidationError):
            DossierPropertyWrite(label="\t  ")

    def test_link_requires_http_or_https_url(self) -> None:
        for url in ("javascript:alert(1)", "file:///tmp/test", "example.org"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                DossierItemCreateRequest(item_type=DossierItemType.link, link_url=url)

        payload = DossierItemCreateRequest(
            item_type=DossierItemType.link,
            link_title="Hersteller",
            link_url="https://example.org/service",
        )
        self.assertEqual(payload.link_url, "https://example.org/service")

    def test_document_item_requires_document_id(self) -> None:
        with self.assertRaises(ValidationError):
            DossierItemCreateRequest(item_type=DossierItemType.document)

        document_id = uuid.uuid4()
        payload = DossierItemCreateRequest(
            item_type=DossierItemType.document,
            document_id=document_id,
        )
        self.assertEqual(payload.document_id, document_id)

    def test_item_order_does_not_accept_negative_positions(self) -> None:
        with self.assertRaises(ValidationError):
            DossierItemPlacement(item_id=uuid.uuid4(), sort_order=-1)

    def test_batch_item_ids_must_be_unique(self) -> None:
        item_id = uuid.uuid4()
        with self.assertRaises(ValidationError):
            DossierItemsDeleteRequest(item_ids=[item_id, item_id])

    def test_restore_snapshot_keeps_stable_id_and_position(self) -> None:
        item_id = uuid.uuid4()
        payload = DossierItemsRestoreRequest(
            items=[
                DossierItemRestoreWrite(
                    id=item_id,
                    item_type=DossierItemType.note,
                    sort_order=2000,
                    pos_x=52,
                    pos_y=104,
                    note_title="Prüfen",
                )
            ]
        )

        self.assertEqual(payload.items[0].id, item_id)
        self.assertEqual(payload.items[0].pos_y, 104)

    def test_restore_document_requires_document_id(self) -> None:
        with self.assertRaises(ValidationError):
            DossierItemRestoreWrite(
                id=uuid.uuid4(),
                item_type=DossierItemType.document,
                sort_order=1000,
            )

    def test_note_connection_target_is_serialized_for_create_and_update(self) -> None:
        target_id = uuid.uuid4()
        created = DossierItemCreateRequest(
            item_type=DossierItemType.note,
            attached_to_item_id=target_id,
        )
        updated = DossierItemUpdateRequest(attached_to_item_id=None)

        self.assertEqual(created.attached_to_item_id, target_id)
        self.assertEqual(updated.model_dump(exclude_unset=True), {"attached_to_item_id": None})

    def test_document_cannot_be_connected_as_a_source(self) -> None:
        with self.assertRaises(ValidationError):
            DossierItemCreateRequest(
                item_type=DossierItemType.document,
                document_id=uuid.uuid4(),
                attached_to_item_id=uuid.uuid4(),
            )

    def test_overview_preview_fields_and_favorite_are_serialized(self) -> None:
        document_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        item = DossierListItem(
            id=uuid.uuid4(),
            title="Auto",
            state="active",
            is_favorite=True,
            created_at=now,
            updated_at=now,
            document_count=1,
            item_count=2,
            group_count=1,
            preview_document_ids=[document_id],
            groups=[DossierGroupSummary(name="Werkstatt", count=2)],
            top_note="Termin HU: 14. Mai",
        )

        self.assertTrue(item.is_favorite)
        self.assertEqual(item.preview_document_ids, [document_id])
        self.assertEqual(item.groups[0].name, "Werkstatt")
        self.assertEqual(item.top_note, "Termin HU: 14. Mai")

    def test_favorite_can_be_changed_without_other_dossier_fields(self) -> None:
        payload = DossierUpdateRequest(is_favorite=False)
        self.assertEqual(payload.model_dump(exclude_unset=True), {"is_favorite": False})

    def test_duplicate_endpoint_is_registered_as_post(self) -> None:
        from app.routers.dossiers import router

        matches = [
            route
            for route in router.routes
            if route.path == "/api/dossiers/{dossier_id}/duplicate"
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("POST", matches[0].methods)

    def test_batch_undo_endpoints_are_registered(self) -> None:
        from app.routers.dossiers import router

        paths = {route.path: route.methods for route in router.routes}
        self.assertIn("POST", paths["/api/dossiers/{dossier_id}/items/batch-delete"])
        self.assertIn("POST", paths["/api/dossiers/{dossier_id}/items/batch-restore"])


if __name__ == "__main__":
    unittest.main()
