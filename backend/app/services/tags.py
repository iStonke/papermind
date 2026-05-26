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
from app.services.utils import is_unique_violation, normalize_name

logger = logging.getLogger("papermind.tags")


class TagService:
    def __init__(self, db: Session):
        self.db = db

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
            rows = self.db.execute(stmt).all()
            return [
                TagRead.model_validate(tag, from_attributes=True).model_copy(
                    update={"usage_count": usage_count}
                )
                for tag, usage_count in rows
            ]

        stmt = select(Tag).order_by(func.lower(Tag.name).asc())
        tags = self.db.execute(stmt).scalars().all()
        return [TagRead.model_validate(tag, from_attributes=True) for tag in tags]

    def _find_case_insensitive_name_conflict(
        self,
        tag_name: str,
        *,
        exclude_tag_id: uuid.UUID | None = None,
    ) -> Tag | None:
        stmt = select(Tag).where(func.lower(Tag.name) == tag_name.lower())
        if exclude_tag_id is not None:
            stmt = stmt.where(Tag.id != exclude_tag_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_tag(self, payload: TagCreateRequest) -> Tag:
        tag_name = normalize_name(payload.name)
        if not tag_name:
            raise BadRequestError("Tag name must not be empty")

        if self._find_case_insensitive_name_conflict(tag_name) is not None:
            raise ConflictError("Tag name already exists", details={"name": tag_name})

        tag = Tag(name=tag_name)
        self.db.add(tag)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Tag name already exists", details={"name": tag_name}) from exc
            raise

        self.db.refresh(tag)
        logger.info("tag created id=%s", tag.id)
        return tag

    def get_tag_or_404(self, tag_id: uuid.UUID) -> Tag:
        tag = self.db.get(Tag, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found", details={"tag_id": str(tag_id)})
        return tag

    def update_tag(self, tag_id: uuid.UUID, payload: TagUpdateRequest) -> Tag:
        tag = self.get_tag_or_404(tag_id)
        tag_name = normalize_name(payload.name)
        if not tag_name:
            raise BadRequestError("Tag name must not be empty")

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
        self.db.delete(tag)
        self.db.commit()
        logger.info("tag deleted id=%s", tag_id)
