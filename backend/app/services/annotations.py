import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.annotation import Annotation
from app.models.document import Document
from app.schemas.annotations import AnnotationCreateRequest, AnnotationUpdateRequest

logger = logging.getLogger("papermind.annotations")


class AnnotationService:
    """CRUD für Seiten-Markierungen. Eigentum wird über das Parent-Dokument
    erzwungen (explizit per Owner-Join, damit es auch ohne RLS-Rolle greift –
    z. B. in Tests). ``owner_id=None`` (Worker/System) sieht keine Zeilen."""

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    # ── intern ────────────────────────────────────────────────────────────────

    def _require_owned_document(self, document_id: uuid.UUID) -> Document:
        document = self.db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.owner_id == self.owner_id,
            )
        ).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found")
        return document

    @staticmethod
    def _title_for(document: Document) -> str:
        return document.display_name or document.original_filename

    def _attach_target_titles(self, annotations: list[Annotation]) -> None:
        """Setzt den transienten Anzeigetitel des Verknüpfungsziels (für die UI)."""
        for annotation in annotations:
            annotation.target_document_title = None
        target_ids = {a.target_document_id for a in annotations if a.target_document_id}
        if not target_ids:
            return
        rows = self.db.execute(
            select(Document.id, Document.display_name, Document.original_filename).where(
                Document.id.in_(target_ids),
                Document.owner_id == self.owner_id,
            )
        ).all()
        titles = {row.id: (row.display_name or row.original_filename) for row in rows}
        for annotation in annotations:
            if annotation.target_document_id:
                annotation.target_document_title = titles.get(annotation.target_document_id)

    def _require_owned_annotation(self, annotation_id: uuid.UUID) -> Annotation:
        annotation = self.db.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Annotation.id == annotation_id,
                Document.owner_id == self.owner_id,
            )
        ).scalar_one_or_none()
        if annotation is None:
            raise NotFoundError("Annotation not found")
        return annotation

    # ── öffentlich ─────────────────────────────────────────────────────────────

    def list_by_document(self, document_id: uuid.UUID) -> list[Annotation]:
        self._require_owned_document(document_id)
        items = list(
            self.db.execute(
                select(Annotation)
                .where(Annotation.document_id == document_id)
                .order_by(Annotation.page.asc(), Annotation.created_at.asc())
            ).scalars()
        )
        self._attach_target_titles(items)
        return items

    def create(self, document_id: uuid.UUID, payload: AnnotationCreateRequest) -> Annotation:
        self._require_owned_document(document_id)
        if payload.target_document_id is not None:
            # Verknüpfungsziel muss demselben Owner gehören.
            self._require_owned_document(payload.target_document_id)

        annotation = Annotation(
            document_id=document_id,
            page=payload.page,
            kind=payload.kind.value,
            color=payload.color,
            rects=[rect.model_dump() for rect in payload.rects],
            quote=payload.quote,
            prefix=payload.prefix,
            suffix=payload.suffix,
            comment=payload.comment,
            target_document_id=payload.target_document_id,
            target_url=payload.target_url,
        )
        self.db.add(annotation)
        self.db.commit()
        self.db.refresh(annotation)
        self._attach_target_titles([annotation])
        return annotation

    def update(self, annotation_id: uuid.UUID, payload: AnnotationUpdateRequest) -> Annotation:
        annotation = self._require_owned_annotation(annotation_id)
        fields = payload.model_dump(exclude_unset=True)

        if "target_document_id" in fields and fields["target_document_id"] is not None:
            self._require_owned_document(fields["target_document_id"])

        for key, value in fields.items():
            setattr(annotation, key, value)

        self.db.commit()
        self.db.refresh(annotation)
        self._attach_target_titles([annotation])
        return annotation

    def delete(self, annotation_id: uuid.UUID) -> None:
        annotation = self._require_owned_annotation(annotation_id)
        self.db.delete(annotation)
        self.db.commit()
