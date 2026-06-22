import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.correspondent import Correspondent, CorrespondentAlias, CorrespondentMatcher
from app.models.document import Document
from app.schemas.correspondents import CorrespondentCreateRequest, CorrespondentMatcherCreateRequest, CorrespondentUpdateRequest
from app.services.utils import is_unique_violation, validate_correspondent_alias, validate_correspondent_name

logger = logging.getLogger("papermind.correspondents")


class CorrespondentService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def list_correspondents(
        self,
        include_count: bool = False,
        *,
        kind: str | None = None,
        parent_id: uuid.UUID | None = None,
    ) -> list[Correspondent]:
        stmt = (
            select(Correspondent)
            .options(selectinload(Correspondent.aliases), selectinload(Correspondent.matchers))
            .order_by(func.lower(Correspondent.name).asc())
        )
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        if kind is not None:
            stmt = stmt.where(Correspondent.kind == kind)
        if parent_id is not None:
            stmt = stmt.where(Correspondent.parent_id == parent_id)
        correspondents = self.db.execute(stmt).scalars().all()
        if not include_count:
            return list(correspondents)

        count_stmt = (
            select(Document.correspondent_id, func.count(Document.id))
            .where(Document.correspondent_id.is_not(None), Document.is_deleted.is_(False))
            .group_by(Document.correspondent_id)
        )
        if self.owner_id is not None:
            count_stmt = count_stmt.where(Document.owner_id == self.owner_id)
        counts = dict(self.db.execute(count_stmt).all())
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
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        if exclude_id is not None:
            stmt = stmt.where(Correspondent.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def _has_children(self, correspondent_id: uuid.UUID) -> bool:
        stmt = select(func.count(Correspondent.id)).where(Correspondent.parent_id == correspondent_id)
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        return int(self.db.execute(stmt).scalar_one() or 0) > 0

    def _validate_hierarchy(
        self,
        *,
        entity_id: uuid.UUID | None,
        kind: str | None,
        parent_id: uuid.UUID | None,
    ) -> None:
        """Erzwingt die Zwei-Ebenen-Regel (Person → Organisation).

        ``entity_id`` ist beim Anlegen ``None``. ``kind``/``parent_id`` sind die
        effektiven Zielwerte nach Anwendung des Patches.
        """
        if parent_id is not None:
            if entity_id is not None and parent_id == entity_id:
                raise BadRequestError("A correspondent cannot be its own organization")
            if kind != "person":
                raise BadRequestError("Only persons can be assigned to an organization")
            parent = self._get_owned(parent_id)
            if parent is None:
                raise BadRequestError("Parent organization not found", details={"parent_id": str(parent_id)})
            if parent.kind != "organization":
                raise BadRequestError("Parent correspondent must be an organization")

        # Wer Kinder hat (zugeordnete Personen), muss eine Organisation bleiben.
        if entity_id is not None and kind != "organization" and self._has_children(entity_id):
            raise BadRequestError("A correspondent with assigned persons must stay an organization")

    def _get_owned(self, correspondent_id: uuid.UUID) -> Correspondent | None:
        stmt = select(Correspondent).where(Correspondent.id == correspondent_id)
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_correspondent(self, payload: CorrespondentCreateRequest) -> Correspondent:
        try:
            name = validate_correspondent_name(payload.name)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        existing = self._find_name_conflict(name)
        if existing is not None:
            return existing

        self._validate_hierarchy(entity_id=None, kind=payload.kind, parent_id=payload.parent_id)

        correspondent = Correspondent(
            owner_id=self.owner_id,
            name=name,
            short_name=payload.short_name,
            notes=payload.notes,
            kind=payload.kind,
            parent_id=payload.parent_id,
        )
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
        stmt = (
            select(Correspondent)
            .options(selectinload(Correspondent.aliases), selectinload(Correspondent.matchers))
            .where(Correspondent.id == correspondent_id)
        )
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        correspondent = self.db.execute(stmt).scalar_one_or_none()
        if correspondent is None:
            raise NotFoundError("Correspondent not found", details={"correspondent_id": str(correspondent_id)})
        return correspondent

    def update_correspondent(self, correspondent_id: uuid.UUID, payload: CorrespondentUpdateRequest) -> Correspondent:
        correspondent = self.get_correspondent_or_404(correspondent_id)
        data = payload.model_dump(exclude_unset=True)

        if "name" in data and data["name"] is not None:
            try:
                name = validate_correspondent_name(data["name"])
            except ValueError as exc:
                raise BadRequestError(str(exc)) from exc
            existing = self._find_name_conflict(name, exclude_id=correspondent_id)
            if existing is not None:
                raise ConflictError("Correspondent name already exists", details={"name": name})
            correspondent.name = name
        if "short_name" in data:
            correspondent.short_name = data["short_name"]
        if "notes" in data:
            correspondent.notes = data["notes"]

        # Effektive Zielwerte für kind/parent_id nach dem Patch bestimmen und die
        # Zwei-Ebenen-Regel prüfen, bevor geschrieben wird.
        target_kind = data["kind"] if "kind" in data else correspondent.kind
        target_parent_id = data["parent_id"] if "parent_id" in data else correspondent.parent_id
        if "kind" in data or "parent_id" in data:
            self._validate_hierarchy(
                entity_id=correspondent_id,
                kind=target_kind,
                parent_id=target_parent_id,
            )
        if "kind" in data:
            correspondent.kind = target_kind
        if "parent_id" in data:
            correspondent.parent_id = target_parent_id

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Correspondent name already exists", details={"name": correspondent.name}) from exc
            raise
        return self.get_correspondent_or_404(correspondent_id)

    def delete_correspondent(self, correspondent_id: uuid.UUID) -> None:
        correspondent = self.get_correspondent_or_404(correspondent_id)
        usage_stmt = select(func.count(Document.id)).where(
            Document.correspondent_id == correspondent_id,
            Document.is_deleted.is_(False),
        )
        if self.owner_id is not None:
            usage_stmt = usage_stmt.where(Document.owner_id == self.owner_id)
        usage_count = self.db.execute(usage_stmt).scalar_one()
        if int(usage_count or 0) > 0:
            raise ConflictError(
                "Correspondent is still used by documents",
                details={"correspondent_id": str(correspondent_id), "usage_count": int(usage_count)},
            )
        self.db.delete(correspondent)
        self.db.commit()

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
        return self.get_correspondent_or_404(correspondent_id)

    def delete_alias(self, correspondent_id: uuid.UUID, alias_id: uuid.UUID) -> Correspondent:
        self.get_correspondent_or_404(correspondent_id)
        alias = self.db.get(CorrespondentAlias, alias_id)
        if alias is None or alias.correspondent_id != correspondent_id:
            raise NotFoundError("Correspondent alias not found", details={"alias_id": str(alias_id)})
        self.db.delete(alias)
        self.db.commit()
        return self.get_correspondent_or_404(correspondent_id)

    def add_matcher(self, correspondent_id: uuid.UUID, payload: CorrespondentMatcherCreateRequest) -> Correspondent:
        self.get_correspondent_or_404(correspondent_id)
        existing = self.db.execute(
            select(CorrespondentMatcher).where(
                CorrespondentMatcher.correspondent_id == correspondent_id,
                CorrespondentMatcher.kind == payload.kind,
                CorrespondentMatcher.scope == payload.scope,
                func.lower(CorrespondentMatcher.pattern) == payload.pattern.lower(),
            )
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(
                CorrespondentMatcher(
                    correspondent_id=correspondent_id,
                    kind=payload.kind,
                    pattern=payload.pattern,
                    scope=payload.scope,
                    priority=payload.priority,
                )
            )
            self.db.commit()
        return self.get_correspondent_or_404(correspondent_id)

    def delete_matcher(self, correspondent_id: uuid.UUID, matcher_id: uuid.UUID) -> Correspondent:
        self.get_correspondent_or_404(correspondent_id)
        matcher = self.db.get(CorrespondentMatcher, matcher_id)
        if matcher is None or matcher.correspondent_id != correspondent_id:
            raise NotFoundError("Correspondent matcher not found", details={"matcher_id": str(matcher_id)})
        self.db.delete(matcher)
        self.db.commit()
        return self.get_correspondent_or_404(correspondent_id)

    def rollup_ids(self, correspondent_id: uuid.UUID) -> set[uuid.UUID]:
        """Korrespondent + (falls Organisation) seine zugeordneten Personen.

        Liefert die Menge der ``correspondent_id``-Werte, die beim Filtern auf
        ``correspondent_id`` einbezogen werden sollen (Roll-up Organisation →
        zugehörige Personen). Für Personen ist es nur die eigene ID.
        """
        ids = {correspondent_id}
        child_stmt = select(Correspondent.id).where(Correspondent.parent_id == correspondent_id)
        if self.owner_id is not None:
            child_stmt = child_stmt.where(Correspondent.owner_id == self.owner_id)
        ids.update(self.db.execute(child_stmt).scalars().all())
        return ids

    def correspondent_ids_exist(self, correspondent_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        if not correspondent_ids:
            return set()
        stmt = select(Correspondent.id).where(Correspondent.id.in_(correspondent_ids))
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        return set(self.db.execute(stmt).scalars().all())
