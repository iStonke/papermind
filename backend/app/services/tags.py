import logging
import uuid

from sqlalchemy import delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.document import Document
from app.models.document_tag import document_tags
from app.models.tag import Tag
from app.schemas.tags import TagCreateRequest, TagMergeRequest, TagRead, TagUpdateRequest
from app.services.utils import is_unique_violation, validate_vocab_name

logger = logging.getLogger("papermind.tags")


class TagService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    @staticmethod
    def cleanup_orphan_tags(
        db: Session,
        *,
        candidate_tag_ids: set[uuid.UUID] | None = None,
    ) -> int:
        if candidate_tag_ids is not None and not candidate_tag_ids:
            return 0

        delete_stmt = delete(Tag)
        if candidate_tag_ids is not None:
            delete_stmt = delete_stmt.where(Tag.id.in_(candidate_tag_ids))

        delete_stmt = delete_stmt.where(
            ~select(document_tags.c.document_id).where(document_tags.c.tag_id == Tag.id).exists()
        )
        result = db.execute(delete_stmt)
        return max(result.rowcount or 0, 0)

    def cleanup_unused_tags(self, *, dry_run: bool) -> dict[str, object]:
        """Listet (und löscht optional) Tags, die an keinem Dokument hängen.

        "Unbenutzt" = keine Zeile in document_tags (auch nicht zu gelöschten
        Dokumenten). dry_run=True liefert nur die Vorschau, ohne zu löschen, sodass
        Vorschau und tatsächliche Löschung dieselbe Definition verwenden.
        """
        unused_filter = ~select(document_tags.c.document_id).where(
            document_tags.c.tag_id == Tag.id
        ).exists()
        list_stmt = select(Tag.id, Tag.name).where(unused_filter)
        if self.owner_id is not None:
            list_stmt = list_stmt.where(Tag.owner_id == self.owner_id)
        rows = self.db.execute(list_stmt.order_by(Tag.name)).all()
        payload = [{"id": str(tag_id), "name": name} for tag_id, name in rows]

        removed = 0
        if not dry_run and payload:
            # Erneut mit demselben Filter löschen (verhindert Löschen von Tags, die
            # zwischen Vorschau und Bestätigung doch einem Dokument zugeordnet wurden).
            del_stmt = delete(Tag).where(Tag.id.in_([uuid.UUID(t["id"]) for t in payload])).where(unused_filter)
            if self.owner_id is not None:
                del_stmt = del_stmt.where(Tag.owner_id == self.owner_id)
            result = self.db.execute(del_stmt)
            removed = max(result.rowcount or 0, 0)
            self.db.commit()
            logger.info("cleanup_unused_tags removed %d tags", removed)

        return {
            "count": len(payload),
            "removed": removed if not dry_run else 0,
            "dry_run": dry_run,
            "tags": payload,
        }

    def list_tags(self, include_count: bool) -> list[TagRead]:
        if include_count:
            stmt = (
                select(Tag, func.count(Document.id).label("usage_count"))
                .outerjoin(document_tags, Tag.id == document_tags.c.tag_id)
                .outerjoin(
                    Document,
                    (Document.id == document_tags.c.document_id) & (Document.is_deleted.is_(False)),
                )
                .group_by(Tag.id)
                .order_by(func.lower(Tag.name).asc())
            )
            if self.owner_id is not None:
                stmt = stmt.where(Tag.owner_id == self.owner_id)
            rows = self.db.execute(stmt).all()
            return [
                TagRead.model_validate(tag, from_attributes=True).model_copy(
                    update={"usage_count": usage_count}
                )
                for tag, usage_count in rows
            ]

        stmt = select(Tag).order_by(func.lower(Tag.name).asc())
        if self.owner_id is not None:
            stmt = stmt.where(Tag.owner_id == self.owner_id)
        tags = self.db.execute(stmt).scalars().all()
        return [TagRead.model_validate(tag, from_attributes=True) for tag in tags]

    def _find_case_insensitive_name_conflict(
        self,
        tag_name: str,
        *,
        exclude_tag_id: uuid.UUID | None = None,
    ) -> Tag | None:
        stmt = select(Tag).where(func.lower(Tag.name) == tag_name.lower())
        if self.owner_id is not None:
            stmt = stmt.where(Tag.owner_id == self.owner_id)
        if exclude_tag_id is not None:
            stmt = stmt.where(Tag.id != exclude_tag_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_tag(self, payload: TagCreateRequest) -> Tag:
        try:
            tag_name = validate_vocab_name(payload.name, label="Tag name")
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        existing_tag = self._find_case_insensitive_name_conflict(tag_name)
        if existing_tag is not None:
            return existing_tag

        tag = Tag(owner_id=self.owner_id, name=tag_name)
        self.db.add(tag)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                existing_tag = self._find_case_insensitive_name_conflict(tag_name)
                if existing_tag is not None:
                    return existing_tag
                raise ConflictError("Tag name already exists", details={"name": tag_name}) from exc
            raise

        self.db.refresh(tag)
        logger.info("tag created id=%s", tag.id)
        return tag

    def get_tag_or_404(self, tag_id: uuid.UUID) -> Tag:
        tag = self.db.get(Tag, tag_id)
        if tag is None or (self.owner_id is not None and tag.owner_id != self.owner_id):
            raise NotFoundError("Tag not found", details={"tag_id": str(tag_id)})
        return tag

    def update_tag(self, tag_id: uuid.UUID, payload: TagUpdateRequest) -> Tag:
        tag = self.get_tag_or_404(tag_id)
        try:
            tag_name = validate_vocab_name(payload.name, label="Tag name")
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        if self._find_case_insensitive_name_conflict(tag_name, exclude_tag_id=tag_id) is not None:
            raise ConflictError("Tag name already exists", details={"name": tag_name})

        old_name = tag.name
        tag.name = tag_name

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Tag name already exists", details={"name": tag_name}) from exc
            raise

        self.db.refresh(tag)
        logger.info("tag renamed tag_id=%s old_name=%s new_name=%s", tag.id, old_name, tag.name)
        return tag

    def merge_tag(self, source_id: uuid.UUID, payload: TagMergeRequest) -> Tag:
        target_id = payload.target_id
        if source_id == target_id:
            raise BadRequestError("source_id and target_id must be different")

        source_tag = self.get_tag_or_404(source_id)
        target_tag = self.get_tag_or_404(target_id)
        source_name = source_tag.name
        target_name = target_tag.name

        source_links_before = (
            self.db.scalar(
                select(func.count()).select_from(document_tags).where(document_tags.c.tag_id == source_id)
            )
            or 0
        )
        target_links_before = (
            self.db.scalar(
                select(func.count()).select_from(document_tags).where(document_tags.c.tag_id == target_id)
            )
            or 0
        )

        transfer_stmt = (
            pg_insert(document_tags)
            .from_select(
                ["document_id", "tag_id"],
                select(document_tags.c.document_id, literal(target_id)).where(document_tags.c.tag_id == source_id),
            )
            .on_conflict_do_nothing(index_elements=["document_id", "tag_id"])
        )
        transfer_result = self.db.execute(transfer_stmt)
        transferred_links = max(transfer_result.rowcount or 0, 0)

        self.db.execute(delete(document_tags).where(document_tags.c.tag_id == source_id))
        self.db.execute(delete(Tag).where(Tag.id == source_id))
        self.db.commit()

        self.db.refresh(target_tag)
        target_links_after = (
            self.db.scalar(
                select(func.count()).select_from(document_tags).where(document_tags.c.tag_id == target_id)
            )
            or 0
        )
        logger.info(
            "tag merged source_id=%s source_name=%s target_id=%s target_name=%s source_links=%s target_links_before=%s target_links_after=%s transferred_links=%s",
            source_id,
            source_name,
            target_id,
            target_name,
            source_links_before,
            target_links_before,
            target_links_after,
            transferred_links,
        )
        return target_tag

    def delete_tag(self, tag_id: uuid.UUID) -> None:
        tag = self.get_tag_or_404(tag_id)
        self.db.execute(delete(document_tags).where(document_tags.c.tag_id == tag_id))
        self.db.delete(tag)
        self.db.commit()
        logger.info("tag deleted id=%s", tag_id)
