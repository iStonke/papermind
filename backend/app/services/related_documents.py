"""Metadata-only document recommendations, ranked within the current owner."""
from __future__ import annotations

import uuid

from sqlalchemy import case, false, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.document import Document
from app.models.document_tag import document_tags
from app.models.tag import Tag
from app.schemas.documents import RelatedDocumentListResponse, RelatedDocumentRead


class RelatedDocumentService:
    def __init__(self, db: Session, owner_id: uuid.UUID) -> None:
        self.db = db
        self.owner_id = owner_id

    def list(self, document_id: uuid.UUID, limit: int = 5) -> RelatedDocumentListResponse:
        source = self.db.execute(select(
            Document.id, Document.document_type, Document.correspondent_id,
        ).where(
            Document.id == document_id,
            Document.owner_id == self.owner_id,
            Document.is_deleted.is_(False),
        )).one_or_none()
        if source is None:
            raise NotFoundError("Document not found")
        tag_ids = self.db.execute(select(Tag.id).join(
            document_tags, document_tags.c.tag_id == Tag.id,
        ).where(
            document_tags.c.document_id == document_id, Tag.owner_id == self.owner_id,
        )).scalars().all()
        if not tag_ids and source.correspondent_id is None:
            # A type on its own (e.g. "invoice") is too broad to be useful.
            return RelatedDocumentListResponse()

        matches = select(
            document_tags.c.document_id,
            func.count().label("shared_count"),
        ).where(document_tags.c.tag_id.in_(tag_ids)).group_by(document_tags.c.document_id).subquery()
        shared = func.coalesce(matches.c.shared_count, 0)
        same_correspondent = (
            Document.correspondent_id == source.correspondent_id
            if source.correspondent_id is not None else false()
        )
        source_type = (source.document_type or "").strip().lower()
        same_type = (
            func.lower(func.trim(Document.document_type)) == source_type
            if source_type else false()
        )
        # Corresp.+type > three tags; several tags > a correspondent alone.
        # Cap tag influence so documents with many generic labels cannot dominate.
        score = (
            case((same_correspondent, 6), else_=0)
            + case((same_type, 2), else_=0)
            + 4 * case((shared > 3, 3), else_=shared)
            + case((same_correspondent & same_type, 6), else_=0)
        )
        rows = self.db.execute(select(
            Document.id, Document.original_filename, Document.display_name, Document.document_date,
            same_correspondent.label("same_correspondent"), same_type.label("same_type"),
            shared.label("shared_tag_count"),
        ).outerjoin(matches, matches.c.document_id == Document.id).where(
            Document.owner_id == self.owner_id,
            Document.is_deleted.is_(False), Document.id != document_id,
            or_(same_correspondent, shared > 0),
        ).order_by(
            score.desc(), Document.document_date.desc().nullslast(),
            Document.created_at.desc(), Document.id,
        ).limit(max(1, min(limit, 10)))).all()
        names: dict[uuid.UUID, list[str]] = {row.id: [] for row in rows}
        if rows and tag_ids:
            shared_names = self.db.execute(select(document_tags.c.document_id, Tag.name).join(
                Tag, Tag.id == document_tags.c.tag_id,
            ).where(
                document_tags.c.document_id.in_(names), document_tags.c.tag_id.in_(tag_ids),
                Tag.owner_id == self.owner_id,
            ).order_by(Tag.name)).all()
            for doc_id, name in shared_names:
                if len(names[doc_id]) < 3:
                    names[doc_id].append(name)
        return RelatedDocumentListResponse(items=[RelatedDocumentRead(
            id=row.id, title=(row.display_name or "").strip() or row.original_filename,
            document_date=row.document_date,
            same_correspondent=bool(row.same_correspondent), same_type=bool(row.same_type),
            shared_tag_count=row.shared_tag_count, shared_tags=names[row.id],
        ) for row in rows])
