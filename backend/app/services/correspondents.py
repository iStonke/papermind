import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.correspondent import Correspondent, CorrespondentAlias, CorrespondentMatcher
from app.models.document import Document
from app.schemas.correspondents import CorrespondentCreateRequest
from app.services.utils import is_unique_violation, validate_correspondent_alias, validate_correspondent_name

logger = logging.getLogger("papermind.correspondents")


class CorrespondentService:
    def __init__(self, db: Session):
        self.db = db

    def list_correspondents(self, include_count: bool = False) -> list[Correspondent]:
        stmt = (
            select(Correspondent)
            .options(selectinload(Correspondent.aliases))
            .order_by(func.lower(Correspondent.name).asc())
        )
        correspondents = self.db.execute(stmt).scalars().all()
        if not include_count:
            return list(correspondents)

        counts = dict(
            self.db.execute(
                select(Document.correspondent_id, func.count(Document.id))
                .where(Document.correspondent_id.is_not(None), Document.is_deleted.is_(False))
                .group_by(Document.correspondent_id)
            ).all()
        )
        for correspondent in correspondents:
            # usage_count ist kein ORM-Feld; als transientes Attribut für die
            # from_attributes-Serialisierung anhängen.
            correspondent.usage_count = int(counts.get(correspondent.id, 0))
        return list(correspondents)

    def _find_name_conflict(
        self,
        name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> Correspondent | None:
        stmt = select(Correspondent).where(func.lower(Correspondent.name) == name.lower())
        if exclude_id is not None:
            stmt = stmt.where(Correspondent.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_correspondent(self, payload: CorrespondentCreateRequest) -> Correspondent:
        try:
            name = validate_correspondent_name(payload.name)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        existing = self._find_name_conflict(name)
        if existing is not None:
            return existing

        correspondent = Correspondent(name=name, short_name=payload.short_name, notes=payload.notes)
        self.db.add(correspondent)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                existing = self._find_name_conflict(name)
                if existing is not None:
                    return existing
                raise ConflictError("Correspondent name already exists", details={"name": name}) from exc
            raise

        self.db.refresh(correspondent)
        logger.info("correspondent created id=%s", correspondent.id)
        return correspondent

    def get_correspondent_or_404(self, correspondent_id: uuid.UUID) -> Correspondent:
        correspondent = self.db.get(Correspondent, correspondent_id)
        if correspondent is None:
            raise NotFoundError("Correspondent not found", details={"correspondent_id": str(correspondent_id)})
        return correspondent

    def add_alias(self, correspondent_id: uuid.UUID, alias: str) -> Correspondent:
        correspondent = self.get_correspondent_or_404(correspondent_id)
        try:
            normalized = validate_correspondent_alias(alias)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        existing_alias = self.db.execute(
            select(CorrespondentAlias).where(
                CorrespondentAlias.correspondent_id == correspondent_id,
                func.lower(CorrespondentAlias.alias) == normalized.lower(),
            )
        ).scalar_one_or_none()
        if existing_alias is None:
            self.db.add(CorrespondentAlias(correspondent_id=correspondent_id, alias=normalized))

        # Parität zum Seed: jeder Alias greift zusätzlich als contains-Matcher in
        # Dateinamen und OCR-Text.
        existing_matcher = self.db.execute(
            select(CorrespondentMatcher).where(
                CorrespondentMatcher.correspondent_id == correspondent_id,
                CorrespondentMatcher.kind == "contains",
                func.lower(CorrespondentMatcher.pattern) == normalized.lower(),
            )
        ).scalar_one_or_none()
        if existing_matcher is None:
            self.db.add(
                CorrespondentMatcher(
                    correspondent_id=correspondent_id,
                    kind="contains",
                    pattern=normalized,
                    scope="both",
                    priority=100,
                )
            )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                # Alias wurde nebenläufig angelegt – kein Fehler, idempotent.
                return self.get_correspondent_or_404(correspondent_id)
            raise

        self.db.refresh(correspondent)
        logger.info("correspondent alias added correspondent_id=%s alias=%s", correspondent_id, normalized)
        return correspondent

    def correspondent_ids_exist(self, correspondent_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        if not correspondent_ids:
            return set()
        return set(
            self.db.execute(
                select(Correspondent.id).where(Correspondent.id.in_(correspondent_ids))
            ).scalars().all()
        )
