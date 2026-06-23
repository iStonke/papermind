import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.document import Document
from app.models.document_type import DocumentType
from app.schemas.document_types import DocumentTypeCreateRequest, DocumentTypeRead, DocumentTypeUpdateRequest
from app.services.utils import is_unique_violation, validate_vocab_name

logger = logging.getLogger("papermind.document_types")


def load_active_document_type_vocab(
    db: Session, owner_id: uuid.UUID | None = None, limit: int = 120
) -> list[tuple[str, str | None]]:
    """Aktive Dokumenttypen als ``(name, prompt_hint)``-Paare laden.

    Best effort: schlägt der DB-Zugriff fehl, wird eine leere Liste geliefert,
    damit Klassifizierung und Vorschau weiterhin auf ihre Fallbacks zurückfallen
    können, statt zu scheitern. ``owner_id`` scopet das Vokabular auf einen Benutzer.
    """
    try:
        stmt = (
            select(DocumentType.name, DocumentType.prompt_hint)
            .where(DocumentType.is_active.is_(True))
            .order_by(DocumentType.sort_order.asc(), func.lower(DocumentType.name).asc())
            .limit(limit)
        )
        if owner_id is not None:
            stmt = stmt.where(DocumentType.owner_id == owner_id)
        rows = db.execute(stmt).all()
    except Exception as exc:  # noqa: BLE001 - vocab loading darf nie der Blocker sein
        logger.warning("could not load active document type vocab: %s", exc)
        return []
    vocab: list[tuple[str, str | None]] = []
    for name, hint in rows:
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        clean_hint = " ".join(str(hint or "").split()).strip() or None
        vocab.append((clean_name, clean_hint))
    return vocab


def document_type_names(vocab: list[tuple[str, str | None]]) -> list[str]:
    return [name for name, _ in vocab]


def document_type_hint_map(vocab: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name: hint for name, hint in vocab if hint}


class DocumentTypeService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def list_document_types(self, include_count: bool) -> list[DocumentTypeRead]:
        if include_count:
            doc_join = (Document.document_type == DocumentType.name) & (Document.is_deleted.is_(False))
            if self.owner_id is not None:
                doc_join = doc_join & (Document.owner_id == self.owner_id)
            stmt = (
                select(DocumentType, func.count(Document.id).label("usage_count"))
                .outerjoin(Document, doc_join)
                .group_by(DocumentType.id)
                .order_by(DocumentType.is_active.desc(), DocumentType.sort_order.asc(), func.lower(DocumentType.name).asc())
            )
            if self.owner_id is not None:
                stmt = stmt.where(DocumentType.owner_id == self.owner_id)
            rows = self.db.execute(stmt).all()
            return [
                DocumentTypeRead.model_validate(document_type, from_attributes=True).model_copy(
                    update={"usage_count": usage_count}
                )
                for document_type, usage_count in rows
            ]

        stmt = select(DocumentType).order_by(DocumentType.is_active.desc(), DocumentType.sort_order.asc(), func.lower(DocumentType.name).asc())
        if self.owner_id is not None:
            stmt = stmt.where(DocumentType.owner_id == self.owner_id)
        document_types = self.db.execute(stmt).scalars().all()
        return [DocumentTypeRead.model_validate(document_type, from_attributes=True) for document_type in document_types]

    def _find_case_insensitive_name_conflict(
        self,
        document_type_name: str,
        *,
        exclude_document_type_id: uuid.UUID | None = None,
    ) -> DocumentType | None:
        stmt = select(DocumentType).where(func.lower(DocumentType.name) == document_type_name.lower())
        if self.owner_id is not None:
            stmt = stmt.where(DocumentType.owner_id == self.owner_id)
        if exclude_document_type_id is not None:
            stmt = stmt.where(DocumentType.id != exclude_document_type_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_document_type(self, payload: DocumentTypeCreateRequest) -> DocumentType:
        try:
            document_type_name = validate_vocab_name(payload.name, label="Document type name")
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        existing = self._find_case_insensitive_name_conflict(document_type_name)
        if existing is not None:
            return existing

        document_type = DocumentType(
            owner_id=self.owner_id,
            name=document_type_name,
            naming_template=payload.naming_template,
            prompt_hint=payload.prompt_hint,
            area=payload.area,
            is_active=payload.is_active,
            sort_order=payload.sort_order,
        )
        self.db.add(document_type)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                existing = self._find_case_insensitive_name_conflict(document_type_name)
                if existing is not None:
                    return existing
                raise ConflictError("Document type name already exists", details={"name": document_type_name}) from exc
            raise

        self.db.refresh(document_type)
        logger.info("document type created id=%s", document_type.id)
        return document_type

    def get_document_type_or_404(self, document_type_id: uuid.UUID) -> DocumentType:
        document_type = self.db.get(DocumentType, document_type_id)
        if document_type is None or (
            self.owner_id is not None and document_type.owner_id != self.owner_id
        ):
            raise NotFoundError("Document type not found", details={"document_type_id": str(document_type_id)})
        return document_type

    def update_document_type(self, document_type_id: uuid.UUID, payload: DocumentTypeUpdateRequest) -> DocumentType:
        document_type = self.get_document_type_or_404(document_type_id)
        old_name = document_type.name
        document_type_name = payload.name
        if document_type_name is not None:
            try:
                document_type_name = validate_vocab_name(document_type_name, label="Document type name")
            except ValueError as exc:
                raise BadRequestError(str(exc)) from exc

            if self._find_case_insensitive_name_conflict(
                document_type_name,
                exclude_document_type_id=document_type_id,
            ) is not None:
                raise ConflictError("Document type name already exists", details={"name": document_type_name})

            document_type.name = document_type_name

        fields_set = payload.model_fields_set
        if "naming_template" in fields_set:
            document_type.naming_template = payload.naming_template
        if "prompt_hint" in fields_set:
            document_type.prompt_hint = payload.prompt_hint
        if "area" in fields_set:
            document_type.area = payload.area
        if payload.is_active is not None:
            document_type.is_active = payload.is_active
        if payload.sort_order is not None:
            document_type.sort_order = payload.sort_order

        try:
            if document_type_name is not None and old_name != document_type_name:
                rename_stmt = update(Document).where(Document.document_type == old_name)
                if self.owner_id is not None:
                    rename_stmt = rename_stmt.where(Document.owner_id == self.owner_id)
                self.db.execute(rename_stmt.values(document_type=document_type_name))
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Document type name already exists", details={"name": document_type_name}) from exc
            raise

        self.db.refresh(document_type)
        logger.info("document type renamed id=%s old_name=%s new_name=%s", document_type.id, old_name, document_type.name)
        return document_type

    def delete_document_type(self, document_type_id: uuid.UUID) -> None:
        document_type = self.get_document_type_or_404(document_type_id)
        self.db.delete(document_type)
        self.db.commit()
        logger.info("document type deleted id=%s", document_type_id)
