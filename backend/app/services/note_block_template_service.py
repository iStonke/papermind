import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.note_block_template import NoteBlockTemplate
from app.schemas.notes import (
    NoteBlockTemplateCreateRequest,
    NoteBlockTemplateUpdateRequest,
)


def _clean_fields(fields) -> list[dict]:
    """Normalisiert die Feldliste auf {"label", "hint"} (getrimmt)."""
    cleaned: list[dict] = []
    for field in fields or []:
        label = (getattr(field, "label", "") or "").strip()
        hint = (getattr(field, "hint", "") or "").strip()
        cleaned.append({"label": label, "hint": hint})
    return cleaned


class NoteBlockTemplateService:
    """CRUD für owner-scoped Baustein-Vorlagen (Feldblöcke)."""

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def _get(self, template_id: uuid.UUID) -> NoteBlockTemplate | None:
        return self.db.scalar(
            select(NoteBlockTemplate).where(
                NoteBlockTemplate.id == template_id,
                NoteBlockTemplate.owner_id == self.owner_id,
            )
        )

    def list(self) -> list[NoteBlockTemplate]:
        stmt = (
            select(NoteBlockTemplate)
            .where(NoteBlockTemplate.owner_id == self.owner_id)
            .order_by(NoteBlockTemplate.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def create(self, payload: NoteBlockTemplateCreateRequest) -> NoteBlockTemplate:
        template = NoteBlockTemplate(
            owner_id=self.owner_id,
            name=(payload.name or "").strip(),
            title=(payload.title or "").strip(),
            color=(payload.color or "teal").strip() or "teal",
            fields=_clean_fields(payload.fields),
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def update(
        self, template_id: uuid.UUID, payload: NoteBlockTemplateUpdateRequest
    ) -> NoteBlockTemplate | None:
        template = self._get(template_id)
        if template is None:
            return None
        if payload.name is not None:
            template.name = payload.name.strip()
        if payload.title is not None:
            template.title = payload.title.strip()
        if payload.color is not None:
            template.color = payload.color.strip() or "teal"
        if payload.fields is not None:
            template.fields = _clean_fields(payload.fields)
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template_id: uuid.UUID) -> bool:
        template = self._get(template_id)
        if template is None:
            return False
        self.db.delete(template)
        self.db.commit()
        return True
