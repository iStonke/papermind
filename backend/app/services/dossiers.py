import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.dossier import Dossier, DossierGroup, DossierItem, DossierProperty
from app.schemas.dossiers import (
    DossierCreateRequest,
    DossierDocumentSummary,
    DossierDocumentsAddRequest,
    DossierGroupCreateRequest,
    DossierGroupSummary,
    DossierGroupUpdateRequest,
    DossierItemCreateRequest,
    DossierItemRead,
    DossierItemsDeleteRequest,
    DossierItemsReorderRequest,
    DossierItemsRestoreRequest,
    DossierItemType,
    DossierItemUpdateRequest,
    DossierListItem,
    DossierPropertyRead,
    DossierPropertyWrite,
    DossierRead,
    DossierUpdateRequest,
)
from app.services.dossier_images import DossierImageStorage


ORDER_STEP = 1000


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class DossierService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id
        self.image_storage = DossierImageStorage()

    def _owned_dossier_stmt(self, dossier_id: uuid.UUID):
        return (
            select(Dossier)
            .options(selectinload(Dossier.properties), selectinload(Dossier.groups))
            .where(Dossier.id == dossier_id, Dossier.owner_id == self.owner_id)
        )

    def get_dossier_or_404(self, dossier_id: uuid.UUID) -> Dossier:
        dossier = self.db.execute(self._owned_dossier_stmt(dossier_id)).scalar_one_or_none()
        if dossier is None:
            raise NotFoundError("Akte nicht gefunden", details={"dossier_id": str(dossier_id)})
        return dossier

    def _require_group(self, dossier_id: uuid.UUID, group_id: uuid.UUID | None) -> DossierGroup | None:
        if group_id is None:
            return None
        group = self.db.execute(
            select(DossierGroup).where(
                DossierGroup.id == group_id,
                DossierGroup.dossier_id == dossier_id,
            )
        ).scalar_one_or_none()
        if group is None:
            raise NotFoundError("Aktengruppe nicht gefunden", details={"group_id": str(group_id)})
        return group

    def _require_item(self, dossier_id: uuid.UUID, item_id: uuid.UUID) -> DossierItem:
        self.get_dossier_or_404(dossier_id)
        item = self.db.execute(
            select(DossierItem).where(DossierItem.id == item_id, DossierItem.dossier_id == dossier_id)
        ).scalar_one_or_none()
        if item is None:
            raise NotFoundError("Aktenelement nicht gefunden", details={"item_id": str(item_id)})
        return item

    def _validate_attachment_target(
        self,
        dossier_id: uuid.UUID,
        source_type: str,
        target_item_id: uuid.UUID | None,
    ) -> None:
        if target_item_id is None:
            return
        if source_type not in {DossierItemType.note.value, DossierItemType.link.value}:
            raise BadRequestError("Nur Notizen und Links können mit einem Dokument verbunden werden")
        target = self.db.execute(
            select(DossierItem).where(
                DossierItem.id == target_item_id,
                DossierItem.dossier_id == dossier_id,
            )
        ).scalar_one_or_none()
        if target is None or target.item_type != DossierItemType.document.value:
            raise BadRequestError("Das Verbindungsziel muss ein Dokument dieses Leuchttisches sein")

    @staticmethod
    def _touch(dossier: Dossier) -> None:
        dossier.updated_at = datetime.now(timezone.utc)

    def _next_group_order(self, dossier_id: uuid.UUID) -> int:
        current = self.db.scalar(
            select(func.max(DossierGroup.sort_order)).where(DossierGroup.dossier_id == dossier_id)
        )
        return int(current or 0) + ORDER_STEP

    def _next_item_order(self, dossier_id: uuid.UUID, group_id: uuid.UUID | None) -> int:
        stmt = select(func.max(DossierItem.sort_order)).where(DossierItem.dossier_id == dossier_id)
        stmt = stmt.where(DossierItem.group_id == group_id) if group_id else stmt.where(DossierItem.group_id.is_(None))
        return int(self.db.scalar(stmt) or 0) + ORDER_STEP

    @staticmethod
    def _property_model(row: DossierProperty) -> DossierPropertyRead:
        return DossierPropertyRead.model_validate(row, from_attributes=True)

    def _dossier_model(self, dossier: Dossier) -> DossierRead:
        return DossierRead(
            id=dossier.id,
            title=dossier.title,
            dossier_type=dossier.dossier_type,
            reference=dossier.reference,
            description=dossier.description,
            state=dossier.state,
            opened_on=dossier.opened_on,
            closed_on=dossier.closed_on,
            color=dossier.color,
            icon=dossier.icon,
            is_favorite=dossier.is_favorite,
            archived_at=dossier.archived_at,
            created_at=dossier.created_at,
            updated_at=dossier.updated_at,
            properties=[self._property_model(item) for item in dossier.properties],
        )

    def list_dossiers(self, *, include_archived: bool = False, q: str | None = None) -> list[DossierListItem]:
        stmt = select(Dossier).options(selectinload(Dossier.properties)).where(Dossier.owner_id == self.owner_id)
        if not include_archived:
            stmt = stmt.where(Dossier.archived_at.is_(None))
        normalized_q = " ".join((q or "").split()).strip()
        if normalized_q:
            pattern = f"%{normalized_q}%"
            matching_properties = select(DossierProperty.id).where(
                DossierProperty.dossier_id == Dossier.id,
                or_(
                    DossierProperty.label.ilike(pattern),
                    DossierProperty.value_text.ilike(pattern),
                ),
            )
            stmt = stmt.where(
                or_(
                    Dossier.title.ilike(pattern),
                    Dossier.dossier_type.ilike(pattern),
                    Dossier.reference.ilike(pattern),
                    Dossier.description.ilike(pattern),
                    matching_properties.exists(),
                )
            )
        dossiers = list(self.db.execute(stmt.order_by(Dossier.updated_at.desc(), Dossier.title.asc())).scalars())
        if not dossiers:
            return []
        ids = [dossier.id for dossier in dossiers]
        item_rows = self.db.execute(
            select(
                DossierItem.dossier_id,
                func.count(DossierItem.id),
                func.count(DossierItem.document_id),
                func.count(DossierItem.id).filter(DossierItem.item_type == DossierItemType.image.value),
            )
            .where(DossierItem.dossier_id.in_(ids))
            .group_by(DossierItem.dossier_id)
        ).all()
        group_rows = self.db.execute(
            select(DossierGroup.dossier_id, func.count(DossierGroup.id))
            .where(DossierGroup.dossier_id.in_(ids))
            .group_by(DossierGroup.dossier_id)
        ).all()
        item_counts = {row[0]: (int(row[1]), int(row[2]), int(row[3])) for row in item_rows}
        group_counts = {row[0]: int(row[1]) for row in group_rows}

        # Vorschau: erste drei Dokument-Thumbnails je Tisch (in Ablagereihenfolge).
        preview_docs: dict[uuid.UUID, list[uuid.UUID]] = {}
        doc_rows = self.db.execute(
            select(DossierItem.dossier_id, DossierItem.document_id)
            .where(
                DossierItem.dossier_id.in_(ids),
                DossierItem.item_type == "document",
                DossierItem.document_id.isnot(None),
            )
            .order_by(DossierItem.dossier_id, DossierItem.sort_order.asc(), DossierItem.created_at.asc())
        ).all()
        for dossier_id, document_id in doc_rows:
            bucket = preview_docs.setdefault(dossier_id, [])
            if len(bucket) < 3:
                bucket.append(document_id)

        # Benannte Gruppen (Name + Item-Anzahl) je Tisch.
        group_name_rows = self.db.execute(
            select(DossierGroup.dossier_id, DossierGroup.id, DossierGroup.title)
            .where(DossierGroup.dossier_id.in_(ids))
            .order_by(DossierGroup.dossier_id, DossierGroup.sort_order.asc(), DossierGroup.created_at.asc())
        ).all()
        group_ids = [row[1] for row in group_name_rows]
        group_item_counts: dict[uuid.UUID, int] = {}
        if group_ids:
            group_item_counts = {
                row[0]: int(row[1])
                for row in self.db.execute(
                    select(DossierItem.group_id, func.count(DossierItem.id))
                    .where(DossierItem.group_id.in_(group_ids))
                    .group_by(DossierItem.group_id)
                ).all()
            }
        groups_by_dossier: dict[uuid.UUID, list[DossierGroupSummary]] = {}
        for dossier_id, group_id, title in group_name_rows:
            groups_by_dossier.setdefault(dossier_id, []).append(
                DossierGroupSummary(name=title, count=group_item_counts.get(group_id, 0))
            )

        # Oberste (jüngste) Notiz je Tisch als kurzer Zettel-Text.
        top_note: dict[uuid.UUID, str] = {}
        note_rows = self.db.execute(
            select(DossierItem.dossier_id, DossierItem.note_title, DossierItem.note_body)
            .where(DossierItem.dossier_id.in_(ids), DossierItem.item_type == "note")
            .order_by(DossierItem.dossier_id, DossierItem.updated_at.desc())
        ).all()
        for dossier_id, note_title, note_body in note_rows:
            if dossier_id in top_note:
                continue
            snippet = " ".join((note_title or note_body or "").split()).strip()
            if snippet:
                top_note[dossier_id] = snippet[:80]

        return [
            DossierListItem(
                **self._dossier_model(dossier).model_dump(),
                item_count=item_counts.get(dossier.id, (0, 0, 0))[0],
                document_count=item_counts.get(dossier.id, (0, 0, 0))[1],
                image_count=item_counts.get(dossier.id, (0, 0, 0))[2],
                group_count=group_counts.get(dossier.id, 0),
                preview_document_ids=preview_docs.get(dossier.id, []),
                groups=groups_by_dossier.get(dossier.id, []),
                top_note=top_note.get(dossier.id),
            )
            for dossier in dossiers
        ]

    def _replace_properties(self, dossier: Dossier, items: list[DossierPropertyWrite]) -> None:
        dossier.properties.clear()
        for index, payload in enumerate(items):
            dossier.properties.append(
                DossierProperty(
                    label=payload.label,
                    value_type=payload.value_type.value,
                    value_text=payload.value_text if payload.value_type.value == "text" else None,
                    value_date=payload.value_date if payload.value_type.value == "date" else None,
                    value_number=payload.value_number if payload.value_type.value == "number" else None,
                    value_boolean=payload.value_boolean if payload.value_type.value == "boolean" else None,
                    sort_order=(index + 1) * ORDER_STEP,
                )
            )

    def create_dossier(self, payload: DossierCreateRequest) -> Dossier:
        dossier = Dossier(
            owner_id=self.owner_id,
            title=payload.title,
            dossier_type=_clean_optional(payload.dossier_type),
            reference=_clean_optional(payload.reference),
            description=_clean_optional(payload.description),
            state=payload.state.value,
            opened_on=payload.opened_on,
            closed_on=payload.closed_on,
            color=payload.color,
            icon=payload.icon,
        )
        self._replace_properties(dossier, payload.properties)
        self.db.add(dossier)
        self.db.commit()
        return self.get_dossier_or_404(dossier.id)

    def update_dossier(self, dossier_id: uuid.UUID, payload: DossierUpdateRequest) -> Dossier:
        dossier = self.get_dossier_or_404(dossier_id)
        fields = payload.model_dump(exclude_unset=True, exclude={"properties", "archived"})
        if "title" in fields and not fields["title"]:
            raise BadRequestError("Der Aktenname darf nicht leer sein")
        for key, value in fields.items():
            if key == "state" and value is not None:
                value = value.value
            if key in {"dossier_type", "reference", "description"}:
                value = _clean_optional(value)
            setattr(dossier, key, value)
        if payload.properties is not None:
            self._replace_properties(dossier, payload.properties)
        if payload.archived is not None:
            dossier.archived_at = datetime.now(timezone.utc) if payload.archived else None
        if dossier.opened_on and dossier.closed_on and dossier.opened_on > dossier.closed_on:
            raise BadRequestError("Das Abschlussdatum darf nicht vor dem Eröffnungsdatum liegen")
        self._touch(dossier)
        self.db.commit()
        return self.get_dossier_or_404(dossier_id)

    def delete_dossier(self, dossier_id: uuid.UUID) -> None:
        dossier = self.get_dossier_or_404(dossier_id)
        self.db.delete(dossier)
        self.db.commit()

    def duplicate_dossier(self, dossier_id: uuid.UUID) -> Dossier:
        source = self.get_dossier_or_404(dossier_id)
        groups = list(
            self.db.execute(
                select(DossierGroup)
                .where(DossierGroup.dossier_id == dossier_id)
                .order_by(DossierGroup.sort_order.asc(), DossierGroup.created_at.asc())
            ).scalars()
        )
        items = list(
            self.db.execute(
                select(DossierItem)
                .where(DossierItem.dossier_id == dossier_id)
                .order_by(DossierItem.sort_order.asc(), DossierItem.created_at.asc())
            ).scalars()
        )
        clone = Dossier(
            owner_id=self.owner_id,
            title=f"{source.title} (Kopie)"[:240],
            dossier_type=source.dossier_type,
            reference=source.reference,
            description=source.description,
            state=source.state,
            opened_on=source.opened_on,
            closed_on=source.closed_on,
            color=source.color,
            icon=source.icon,
            is_favorite=False,
        )
        for prop in source.properties:
            clone.properties.append(
                DossierProperty(
                    label=prop.label,
                    value_type=prop.value_type,
                    value_text=prop.value_text,
                    value_date=prop.value_date,
                    value_number=prop.value_number,
                    value_boolean=prop.value_boolean,
                    sort_order=prop.sort_order,
                )
            )
        self.db.add(clone)
        self.db.flush()
        group_map: dict[uuid.UUID, uuid.UUID] = {}
        for group in groups:
            new_group = DossierGroup(
                dossier_id=clone.id,
                title=group.title,
                color=group.color,
                sort_order=group.sort_order,
                pos_x=group.pos_x,
                pos_y=group.pos_y,
            )
            self.db.add(new_group)
            self.db.flush()
            group_map[group.id] = new_group.id
        item_pairs: list[tuple[DossierItem, DossierItem]] = []
        for item in items:
            cloned_item = DossierItem(
                dossier_id=clone.id,
                group_id=group_map.get(item.group_id) if item.group_id else None,
                item_type=item.item_type,
                sort_order=item.sort_order,
                pos_x=item.pos_x,
                pos_y=item.pos_y,
                document_id=item.document_id,
                note_title=item.note_title,
                note_body=item.note_body,
                note_color=item.note_color,
                link_title=item.link_title,
                link_url=item.link_url,
                link_description=item.link_description,
                image_filename=item.image_filename,
                image_content_type=item.image_content_type,
                image_file_key=item.image_file_key,
                image_size_bytes=item.image_size_bytes,
                image_width=item.image_width,
                image_height=item.image_height,
            )
            self.db.add(cloned_item)
            item_pairs.append((item, cloned_item))
        self.db.flush()
        item_map = {source.id: cloned.id for source, cloned in item_pairs}
        for source, cloned in item_pairs:
            cloned.attached_to_item_id = item_map.get(source.attached_to_item_id)
        self.db.commit()
        return self.get_dossier_or_404(clone.id)

    def create_group(self, dossier_id: uuid.UUID, payload: DossierGroupCreateRequest) -> DossierGroup:
        dossier = self.get_dossier_or_404(dossier_id)
        group = DossierGroup(
            dossier_id=dossier_id,
            title=payload.title,
            color=payload.color,
            sort_order=self._next_group_order(dossier_id),
            pos_x=payload.pos_x,
            pos_y=payload.pos_y,
        )
        self.db.add(group)
        self._touch(dossier)
        self.db.commit()
        self.db.refresh(group)
        return group

    def update_group(
        self, dossier_id: uuid.UUID, group_id: uuid.UUID, payload: DossierGroupUpdateRequest
    ) -> DossierGroup:
        dossier = self.get_dossier_or_404(dossier_id)
        group = self._require_group(dossier_id, group_id)
        assert group is not None
        for key, value in payload.model_dump(exclude_unset=True).items():
            if key == "title" and not value:
                raise BadRequestError("Der Gruppenname darf nicht leer sein")
            setattr(group, key, value)
        self._touch(dossier)
        self.db.commit()
        self.db.refresh(group)
        return group

    def reorder_groups(self, dossier_id: uuid.UUID, group_ids: list[uuid.UUID]) -> list[DossierGroup]:
        dossier = self.get_dossier_or_404(dossier_id)
        groups = list(
            self.db.execute(
                select(DossierGroup).where(DossierGroup.dossier_id == dossier_id)
            ).scalars()
        )
        by_id = {group.id: group for group in groups}
        if len(group_ids) != len(set(group_ids)) or set(group_ids) != set(by_id):
            raise BadRequestError("Die Gruppenreihenfolge ist unvollständig oder ungültig")
        for index, group_id in enumerate(group_ids):
            by_id[group_id].sort_order = (index + 1) * ORDER_STEP
        self._touch(dossier)
        self.db.commit()
        return sorted(groups, key=lambda group: group.sort_order)

    def delete_group(self, dossier_id: uuid.UUID, group_id: uuid.UUID) -> None:
        dossier = self.get_dossier_or_404(dossier_id)
        group = self._require_group(dossier_id, group_id)
        assert group is not None
        items = list(
            self.db.execute(
                select(DossierItem)
                .where(DossierItem.dossier_id == dossier_id, DossierItem.group_id == group_id)
                .order_by(DossierItem.sort_order.asc())
            ).scalars()
        )
        next_order = self._next_item_order(dossier_id, None)
        for index, item in enumerate(items):
            item.group_id = None
            item.sort_order = next_order + index * ORDER_STEP
        self.db.delete(group)
        self._touch(dossier)
        self.db.commit()

    def _owned_documents(self, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, Document]:
        documents = list(
            self.db.execute(
                select(Document).where(Document.id.in_(document_ids), Document.owner_id == self.owner_id)
            ).scalars()
        )
        by_id = {document.id: document for document in documents}
        if set(document_ids) != set(by_id):
            raise NotFoundError("Mindestens ein Dokument wurde nicht gefunden")
        return by_id

    def add_documents(
        self, dossier_id: uuid.UUID, payload: DossierDocumentsAddRequest
    ) -> tuple[list[DossierItem], list[uuid.UUID]]:
        dossier = self.get_dossier_or_404(dossier_id)
        self._require_group(dossier_id, payload.group_id)
        document_ids = list(dict.fromkeys(payload.document_ids))
        documents = self._owned_documents(document_ids)
        if any(document.is_deleted for document in documents.values()):
            raise BadRequestError("Dokumente aus dem Papierkorb können nicht hinzugefügt werden")
        existing = set(
            self.db.execute(
                select(DossierItem.document_id).where(
                    DossierItem.dossier_id == dossier_id,
                    DossierItem.document_id.in_(document_ids),
                )
            ).scalars()
        )
        next_order = self._next_item_order(dossier_id, payload.group_id)
        created: list[DossierItem] = []
        for index, document_id in enumerate(document_ids):
            if document_id in existing:
                continue
            item = DossierItem(
                dossier_id=dossier_id,
                group_id=payload.group_id,
                item_type=DossierItemType.document.value,
                document_id=document_id,
                sort_order=next_order + index * ORDER_STEP,
            )
            self.db.add(item)
            created.append(item)
        if created:
            self._touch(dossier)
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                raise ConflictError("Mindestens ein Dokument ist bereits in der Akte") from exc
            for item in created:
                self.db.refresh(item)
        return created, [document_id for document_id in document_ids if document_id in existing]

    def create_item(self, dossier_id: uuid.UUID, payload: DossierItemCreateRequest) -> DossierItem:
        dossier = self.get_dossier_or_404(dossier_id)
        self._require_group(dossier_id, payload.group_id)
        if payload.item_type == DossierItemType.document:
            assert payload.document_id is not None
            created, skipped = self.add_documents(
                dossier_id,
                DossierDocumentsAddRequest(document_ids=[payload.document_id], group_id=payload.group_id),
            )
            if skipped:
                raise ConflictError("Das Dokument ist bereits in der Akte")
            return created[0]
        self._validate_attachment_target(dossier_id, payload.item_type.value, payload.attached_to_item_id)
        item = DossierItem(
            dossier_id=dossier_id,
            group_id=payload.group_id,
            item_type=payload.item_type.value,
            attached_to_item_id=payload.attached_to_item_id,
            sort_order=self._next_item_order(dossier_id, payload.group_id),
            pos_x=payload.pos_x,
            pos_y=payload.pos_y,
            note_title=_clean_optional(payload.note_title),
            note_body=payload.note_body,
            note_color=payload.note_color,
            link_title=_clean_optional(payload.link_title),
            link_url=_clean_optional(payload.link_url),
            link_description=_clean_optional(payload.link_description),
        )
        self.db.add(item)
        self._touch(dossier)
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_image_item(self, dossier_id: uuid.UUID, file: UploadFile) -> DossierItem:
        dossier = self.get_dossier_or_404(dossier_id)
        if self.owner_id is None:
            raise BadRequestError("Für Bild-Uploads ist ein Benutzer erforderlich")
        item_id = uuid.uuid4()
        stored = self.image_storage.store(file, owner_id=self.owner_id, item_id=item_id)
        item = DossierItem(
            id=item_id,
            dossier_id=dossier_id,
            item_type=DossierItemType.image.value,
            sort_order=self._next_item_order(dossier_id, None),
            image_filename=stored.filename,
            image_content_type=stored.content_type,
            image_file_key=stored.file_key,
            image_size_bytes=stored.size_bytes,
            image_width=stored.width,
            image_height=stored.height,
        )
        self.db.add(item)
        self._touch(dossier)
        try:
            self.db.commit()
            self.db.refresh(item)
        except Exception:
            self.db.rollback()
            self.image_storage.cleanup(stored.file_key)
            raise
        return item

    def get_image_file(self, dossier_id: uuid.UUID, item_id: uuid.UUID) -> tuple[DossierItem, Path]:
        item = self._require_item(dossier_id, item_id)
        if item.item_type != DossierItemType.image.value or not item.image_file_key:
            raise NotFoundError("Bild wurde nicht gefunden", details={"item_id": str(item_id)})
        path = self.image_storage.resolve_path(item.image_file_key)
        if not path.is_file():
            raise NotFoundError("Bilddatei wurde nicht gefunden", details={"item_id": str(item_id)})
        return item, path

    def update_item(
        self, dossier_id: uuid.UUID, item_id: uuid.UUID, payload: DossierItemUpdateRequest
    ) -> DossierItem:
        dossier = self.get_dossier_or_404(dossier_id)
        item = self._require_item(dossier_id, item_id)
        fields = payload.model_dump(exclude_unset=True)
        if "group_id" in fields:
            self._require_group(dossier_id, fields["group_id"])
        if "attached_to_item_id" in fields:
            self._validate_attachment_target(dossier_id, item.item_type, fields["attached_to_item_id"])
        allowed = {
            "document": {"group_id", "pos_x", "pos_y"},
            "note": {"group_id", "attached_to_item_id", "pos_x", "pos_y", "note_title", "note_body", "note_color"},
            "link": {"group_id", "attached_to_item_id", "pos_x", "pos_y", "link_title", "link_url", "link_description"},
            "image": {"group_id", "pos_x", "pos_y"},
        }[item.item_type]
        if set(fields) - allowed:
            raise BadRequestError("Die Felder passen nicht zum Typ des Aktenelements")
        for key, value in fields.items():
            setattr(item, key, value)
        self._touch(dossier)
        self.db.commit()
        self.db.refresh(item)
        return item

    def reorder_items(self, dossier_id: uuid.UUID, payload: DossierItemsReorderRequest) -> list[DossierItem]:
        dossier = self.get_dossier_or_404(dossier_id)
        ids = [placement.item_id for placement in payload.placements]
        if len(ids) != len(set(ids)):
            raise BadRequestError("Ein Aktenelement darf nur einmal einsortiert werden")
        items = list(
            self.db.execute(
                select(DossierItem).where(DossierItem.dossier_id == dossier_id, DossierItem.id.in_(ids))
            ).scalars()
        )
        by_id = {item.id: item for item in items}
        if set(ids) != set(by_id):
            raise NotFoundError("Mindestens ein Aktenelement wurde nicht gefunden")
        group_ids = {placement.group_id for placement in payload.placements if placement.group_id is not None}
        if group_ids:
            owned_group_ids = set(
                self.db.execute(
                    select(DossierGroup.id).where(
                        DossierGroup.dossier_id == dossier_id,
                        DossierGroup.id.in_(group_ids),
                    )
                ).scalars()
            )
            if group_ids != owned_group_ids:
                raise NotFoundError("Mindestens eine Aktengruppe wurde nicht gefunden")
        for placement in payload.placements:
            item = by_id[placement.item_id]
            item.group_id = placement.group_id
            item.sort_order = placement.sort_order
            item.pos_x = placement.pos_x
            item.pos_y = placement.pos_y
        self._touch(dossier)
        self.db.commit()
        return items

    def delete_item(self, dossier_id: uuid.UUID, item_id: uuid.UUID) -> None:
        dossier = self.get_dossier_or_404(dossier_id)
        item = self._require_item(dossier_id, item_id)
        self.db.delete(item)
        self._touch(dossier)
        self.db.commit()

    def delete_items(self, dossier_id: uuid.UUID, payload: DossierItemsDeleteRequest) -> None:
        dossier = self.get_dossier_or_404(dossier_id)
        ids = list(payload.item_ids)
        items = list(
            self.db.execute(
                select(DossierItem).where(
                    DossierItem.dossier_id == dossier_id,
                    DossierItem.id.in_(ids),
                )
            ).scalars()
        )
        if {item.id for item in items} != set(ids):
            raise NotFoundError("Mindestens ein Aktenelement wurde nicht gefunden")
        for item in items:
            self.db.delete(item)
        self._touch(dossier)
        self.db.commit()

    def restore_items(self, dossier_id: uuid.UUID, payload: DossierItemsRestoreRequest) -> list[DossierItem]:
        """Stellt gelöschte Karten mit stabilen IDs atomar wieder her."""

        dossier = self.get_dossier_or_404(dossier_id)
        snapshots = list(payload.items)
        ids = {snapshot.id for snapshot in snapshots}
        existing_ids = set(
            self.db.execute(select(DossierItem.id).where(DossierItem.id.in_(ids))).scalars()
        )
        if existing_ids:
            raise ConflictError("Mindestens ein Aktenelement existiert bereits")

        group_ids = {snapshot.group_id for snapshot in snapshots if snapshot.group_id is not None}
        if group_ids:
            owned_group_ids = set(
                self.db.execute(
                    select(DossierGroup.id).where(
                        DossierGroup.dossier_id == dossier_id,
                        DossierGroup.id.in_(group_ids),
                    )
                ).scalars()
            )
            if owned_group_ids != group_ids:
                raise NotFoundError("Mindestens eine Aktengruppe wurde nicht gefunden")

        document_snapshots = [
            snapshot for snapshot in snapshots if snapshot.item_type == DossierItemType.document
        ]
        document_ids = [snapshot.document_id for snapshot in document_snapshots]
        if document_ids:
            documents = self._owned_documents(document_ids)
            if any(document.is_deleted for document in documents.values()):
                raise BadRequestError("Dokumente aus dem Papierkorb können nicht wiederhergestellt werden")
            occupied_documents = set(
                self.db.execute(
                    select(DossierItem.document_id).where(
                        DossierItem.dossier_id == dossier_id,
                        DossierItem.document_id.in_(document_ids),
                    )
                ).scalars()
            )
            if occupied_documents:
                raise ConflictError("Mindestens ein Dokument ist bereits in der Akte")

        restored_document_item_ids = {snapshot.id for snapshot in document_snapshots}
        attachment_ids = {
            snapshot.attached_to_item_id
            for snapshot in snapshots
            if snapshot.attached_to_item_id is not None
        }
        external_attachment_ids = attachment_ids - restored_document_item_ids
        if external_attachment_ids:
            valid_external_ids = set(
                self.db.execute(
                    select(DossierItem.id).where(
                        DossierItem.dossier_id == dossier_id,
                        DossierItem.id.in_(external_attachment_ids),
                        DossierItem.item_type == DossierItemType.document.value,
                    )
                ).scalars()
            )
            if valid_external_ids != external_attachment_ids:
                raise BadRequestError("Mindestens ein Verbindungsziel ist ungültig")

        created: list[DossierItem] = []
        # Dokumente zuerst einfügen, damit nachfolgende Notizen/Links ihre sofort
        # geprüften Foreign Keys auf ebenfalls wiederhergestellte Karten setzen können.
        ordered = document_snapshots + [
            snapshot for snapshot in snapshots if snapshot.item_type != DossierItemType.document
        ]
        try:
            for snapshot in ordered:
                item = DossierItem(
                    id=snapshot.id,
                    dossier_id=dossier_id,
                    group_id=snapshot.group_id,
                    item_type=snapshot.item_type.value,
                    sort_order=snapshot.sort_order,
                    pos_x=snapshot.pos_x,
                    pos_y=snapshot.pos_y,
                    document_id=snapshot.document_id,
                    attached_to_item_id=snapshot.attached_to_item_id,
                    note_title=_clean_optional(snapshot.note_title),
                    note_body=snapshot.note_body,
                    note_color=snapshot.note_color,
                    link_title=_clean_optional(snapshot.link_title),
                    link_url=_clean_optional(snapshot.link_url),
                    link_description=_clean_optional(snapshot.link_description),
                    image_filename=snapshot.image_filename,
                    image_content_type=snapshot.image_content_type,
                    image_file_key=snapshot.image_file_key,
                    image_size_bytes=snapshot.image_size_bytes,
                    image_width=snapshot.image_width,
                    image_height=snapshot.image_height,
                )
                self.db.add(item)
                created.append(item)
                if snapshot.item_type == DossierItemType.document:
                    self.db.flush()
            self._touch(dossier)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Die gelöschten Elemente konnten nicht wiederhergestellt werden") from exc

        by_id = {item.id: item for item in created}
        return [by_id[snapshot.id] for snapshot in snapshots]

    def _document_summaries(self, document_ids: set[uuid.UUID]) -> dict[uuid.UUID, DossierDocumentSummary]:
        if not document_ids:
            return {}
        documents = list(
            self.db.execute(
                select(Document).where(Document.id.in_(document_ids), Document.owner_id == self.owner_id)
            ).scalars()
        )
        correspondent_ids = {doc.correspondent_id for doc in documents if doc.correspondent_id}
        correspondent_names = {}
        if correspondent_ids:
            correspondent_names = dict(
                self.db.execute(
                    select(Correspondent.id, Correspondent.name).where(
                        Correspondent.id.in_(correspondent_ids),
                        Correspondent.owner_id == self.owner_id,
                    )
                ).all()
            )
        return {
            document.id: DossierDocumentSummary(
                id=document.id,
                title=document.display_name or document.original_filename,
                original_filename=document.original_filename,
                document_date=document.document_date,
                document_type=document.document_type,
                correspondent_name=correspondent_names.get(document.correspondent_id),
                page_count=document.page_count,
                is_deleted=document.is_deleted,
            )
            for document in documents
        }

    def item_models(self, items: list[DossierItem]) -> list[DossierItemRead]:
        documents = self._document_summaries({item.document_id for item in items if item.document_id})
        return [
            DossierItemRead(
                id=item.id,
                dossier_id=item.dossier_id,
                group_id=item.group_id,
                item_type=item.item_type,
                sort_order=item.sort_order,
                pos_x=item.pos_x,
                pos_y=item.pos_y,
                document_id=item.document_id,
                attached_to_item_id=item.attached_to_item_id,
                document=documents.get(item.document_id),
                note_title=item.note_title,
                note_body=item.note_body,
                note_color=item.note_color,
                link_title=item.link_title,
                link_url=item.link_url,
                link_description=item.link_description,
                image_filename=item.image_filename,
                image_content_type=item.image_content_type,
                image_file_key=item.image_file_key,
                image_size_bytes=item.image_size_bytes,
                image_width=item.image_width,
                image_height=item.image_height,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]

    def board(self, dossier_id: uuid.UUID) -> tuple[DossierRead, list[DossierGroup], list[DossierItemRead]]:
        dossier = self.get_dossier_or_404(dossier_id)
        groups = list(
            self.db.execute(
                select(DossierGroup)
                .where(DossierGroup.dossier_id == dossier_id)
                .order_by(DossierGroup.sort_order.asc(), DossierGroup.created_at.asc())
            ).scalars()
        )
        items = list(
            self.db.execute(
                select(DossierItem)
                .where(DossierItem.dossier_id == dossier_id)
                .order_by(DossierItem.sort_order.asc(), DossierItem.created_at.asc())
            ).scalars()
        )
        return self._dossier_model(dossier), groups, self.item_models(items)
