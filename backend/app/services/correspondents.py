import logging
import uuid
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.correspondent import Correspondent, CorrespondentAlias, CorrespondentMatcher, CorrespondentRelation
from app.models.document import Document
from app.schemas.correspondents import (
    CorrespondentAmountSummary,
    CorrespondentCreateRequest,
    CorrespondentMatcherCreateRequest,
    CorrespondentProfileActivity,
    CorrespondentProfileMember,
    CorrespondentProfileRead,
    CorrespondentRead,
    CorrespondentRelationCreateRequest,
    CorrespondentRelationRead,
    CorrespondentUpdateRequest,
)
from app.services.legal_forms import split_legal_form
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

        stats = self._document_stats()
        for correspondent in correspondents:
            # usage_count/last_document_date sind keine ORM-Felder; als transiente
            # Attribute für die from_attributes-Serialisierung anhängen.
            count, last_date = stats.get(correspondent.id, (0, None))
            correspondent.usage_count = count
            correspondent.last_document_date = last_date
        return list(correspondents)

    def _document_stats(self, correspondent_ids: set[uuid.UUID] | None = None) -> dict[uuid.UUID, tuple[int, date | None]]:
        """Anzahl aktiver Dokumente und jüngstes Dokumentdatum je Korrespondent."""
        stmt = (
            select(Document.correspondent_id, func.count(Document.id), func.max(self._effective_date()))
            .where(Document.correspondent_id.is_not(None), Document.is_deleted.is_(False))
            .group_by(Document.correspondent_id)
        )
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        if correspondent_ids is not None:
            stmt = stmt.where(Document.correspondent_id.in_(correspondent_ids))
        return {cid: (int(count), last) for cid, count, last in self.db.execute(stmt).all()}

    @staticmethod
    def _effective_date():
        # Dokumentdatum, sonst Importdatum – damit auch undatierte Belege zählen.
        return func.coalesce(Document.document_date, func.date(Document.created_at))

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

    def _find_alias_conflict(
        self,
        name: str,
        *,
        exclude_correspondent_id: uuid.UUID | None = None,
    ) -> CorrespondentAlias | None:
        stmt = (
            select(CorrespondentAlias)
            .join(Correspondent, Correspondent.id == CorrespondentAlias.correspondent_id)
            .where(func.lower(CorrespondentAlias.alias) == name.lower())
        )
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        if exclude_correspondent_id is not None:
            stmt = stmt.where(CorrespondentAlias.correspondent_id != exclude_correspondent_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def _child_kinds(self, correspondent_id: uuid.UUID) -> set[str | None]:
        """Typen der direkt zugeordneten Einträge (leer = keine Kinder)."""
        stmt = select(Correspondent.kind).where(Correspondent.parent_id == correspondent_id).distinct()
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        return set(self.db.execute(stmt).scalars().all())

    # Erlaubte übergeordnete Typen je Typ (Sammlung → Organisation → Person).
    _PARENT_KINDS = {"person": {"organization", "collection"}, "organization": {"collection"}}

    def _validate_hierarchy(
        self,
        *,
        entity_id: uuid.UUID | None,
        kind: str | None,
        parent_id: uuid.UUID | None,
    ) -> None:
        """Erzwingt die Hierarchie Sammlung → Organisation → Person.

        Personen gehören zu einer Organisation oder Sammlung, Organisationen zu
        einer Sammlung; Sammlungen und Einträge ohne Typ zu niemandem.
        ``entity_id`` ist beim Anlegen ``None``. ``kind``/``parent_id`` sind die
        effektiven Zielwerte nach Anwendung des Patches.
        """
        if parent_id is not None:
            if entity_id is not None and parent_id == entity_id:
                raise BadRequestError("Ein Korrespondent kann nicht sich selbst zugeordnet werden.")
            allowed = self._PARENT_KINDS.get(kind)
            if not allowed:
                raise BadRequestError("Nur Personen und Organisationen können einem anderen Eintrag zugeordnet werden.")
            parent = self._get_owned(parent_id)
            if parent is None:
                raise BadRequestError(
                    "Der ausgewählte übergeordnete Eintrag wurde nicht gefunden.",
                    details={"parent_id": str(parent_id)},
                )
            if parent.kind not in allowed:
                raise BadRequestError(
                    "Personen gehören zu einer Organisation oder Sammlung, Organisationen zu einer Sammlung."
                )

        # Wer Kinder hat, muss deren Typen weiterhin aufnehmen können.
        if entity_id is not None:
            child_kinds = self._child_kinds(entity_id)
            if child_kinds and not all(kind in self._PARENT_KINDS.get(child, set()) for child in child_kinds):
                raise BadRequestError(
                    "Der Typ kann nicht geändert werden, solange ihm Einträge zugeordnet sind, die dazu nicht passen."
                )

    def _get_owned(self, correspondent_id: uuid.UUID) -> Correspondent | None:
        stmt = select(Correspondent).where(Correspondent.id == correspondent_id)
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        return self.db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _person_name(kind: str | None, first_name: str | None, last_name: str | None) -> str:
        if kind != "person":
            raise BadRequestError("Vor- und Nachname können nur bei Personen gespeichert werden.")
        return " ".join(part for part in (first_name, last_name) if part)

    @staticmethod
    def _default_short_name(payload: CorrespondentCreateRequest, name: str) -> str | None:
        """Ohne ausdrücklichen Kurznamen: Name ohne Rechtsform („Vodafone GmbH" → „Vodafone").

        Ein mitgeschickter Kurzname – auch ``null`` – hat immer Vorrang; Sammlungen
        bekommen keinen Kurznamen.
        """
        if "short_name" in payload.model_fields_set or payload.kind == "collection":
            return payload.short_name
        split = split_legal_form(name)
        return split.base[:60].rstrip() if split.legal_form else None

    def create_correspondent(self, payload: CorrespondentCreateRequest) -> Correspondent:
        name = payload.name
        if payload.first_name is not None or payload.last_name is not None:
            name = self._person_name(payload.kind, payload.first_name, payload.last_name)
        try:
            name = validate_correspondent_name(name)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        existing = self._find_name_conflict(name)
        if existing is not None:
            return existing
        if self._find_alias_conflict(name) is not None:
            raise ConflictError(
                "Dieser Name wird bereits als Alias oder Erkennungsname verwendet.",
                details={"name": name},
            )

        self._validate_hierarchy(entity_id=None, kind=payload.kind, parent_id=payload.parent_id)

        correspondent = Correspondent(
            owner_id=self.owner_id,
            name=name,
            first_name=payload.first_name,
            last_name=payload.last_name,
            short_name=self._default_short_name(payload, name),
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
                raise ConflictError("Ein Korrespondent mit diesem Namen existiert bereits.", details={"name": name}) from exc
            raise

        self.db.refresh(correspondent)
        logger.info("correspondent created id=%s", correspondent.id)
        return correspondent

    def get_correspondent_or_404(self, correspondent_id: uuid.UUID, *, for_update: bool = False) -> Correspondent:
        stmt = (
            select(Correspondent)
            .options(selectinload(Correspondent.aliases), selectinload(Correspondent.matchers))
            .where(Correspondent.id == correspondent_id)
        )
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        correspondent = self.db.execute(stmt).scalar_one_or_none()
        if correspondent is None:
            raise NotFoundError("Korrespondent wurde nicht gefunden.", details={"correspondent_id": str(correspondent_id)})
        return correspondent

    def update_correspondent(self, correspondent_id: uuid.UUID, payload: CorrespondentUpdateRequest) -> Correspondent:
        # Ein Teilname und der daraus abgeleitete Anzeigename müssen zusammenpassen.
        correspondent = self.get_correspondent_or_404(correspondent_id, for_update=True)
        data = payload.model_dump(exclude_unset=True)

        target_kind = data.get("kind", correspondent.kind)
        target_parent_id = data.get("parent_id", correspondent.parent_id)
        name_fields = {"first_name", "last_name"}
        updates_name_parts = bool(name_fields & data.keys())
        name = data.get("name")
        if updates_name_parts:
            if correspondent.first_name is None and correspondent.last_name is None and not name_fields <= data.keys():
                raise BadRequestError("Bitte gib beide Namensfelder für die erste Aufteilung des Namens an.")
            first_name = data.get("first_name", correspondent.first_name)
            last_name = data.get("last_name", correspondent.last_name)
            name = self._person_name(target_kind, first_name, last_name)

        if name is not None:
            try:
                name = validate_correspondent_name(name)
            except ValueError as exc:
                raise BadRequestError(str(exc)) from exc
            existing = self._find_name_conflict(name, exclude_id=correspondent_id)
            if existing is not None:
                raise ConflictError("Ein Korrespondent mit diesem Namen existiert bereits.", details={"name": name})
            if self._find_alias_conflict(name, exclude_correspondent_id=correspondent_id) is not None:
                raise ConflictError(
                    "Dieser Name wird bereits als Alias oder Erkennungsname verwendet.",
                    details={"name": name},
                )
        if "kind" in data or "parent_id" in data:
            self._validate_hierarchy(
                entity_id=correspondent_id,
                kind=target_kind,
                parent_id=target_parent_id,
            )

        if updates_name_parts:
            correspondent.first_name = first_name
            correspondent.last_name = last_name
        elif ("kind" in data and target_kind != "person") or (name is not None and name != correspondent.name):
            correspondent.first_name = None
            correspondent.last_name = None
        if name is not None:
            correspondent.name = name
        if "short_name" in data:
            correspondent.short_name = data["short_name"]
        if "notes" in data:
            correspondent.notes = data["notes"]
        if "kind" in data:
            correspondent.kind = target_kind
        if "parent_id" in data:
            correspondent.parent_id = target_parent_id

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError(
                    "Ein Korrespondent mit diesem Namen existiert bereits.",
                    details={"name": correspondent.name},
                ) from exc
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
                "Der Korrespondent kann nicht gelöscht werden, solange Dokumente zugeordnet sind.",
                details={"correspondent_id": str(correspondent_id), "usage_count": int(usage_count)},
            )
        self.db.delete(correspondent)
        self.db.commit()

    def unlink_documents(self, correspondent_id: uuid.UUID) -> int:
        """Löst alle Dokumentzuordnungen, behält den Korrespondenten aber bei."""
        self.get_correspondent_or_404(correspondent_id)
        stmt = update(Document).where(Document.correspondent_id == correspondent_id)
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        result = self.db.execute(stmt.values(correspondent_id=None))
        self.db.commit()
        count = int(result.rowcount or 0)
        logger.info(
            "correspondent document assignments unlinked correspondent_id=%s count=%s",
            correspondent_id,
            count,
        )
        return count

    def merge_correspondents(self, target_id: uuid.UUID, source_id: uuid.UUID):
        """``source_id`` geht in ``target_id`` auf; liefert Ziel und Zähler der Übernahmen."""
        from app.services.correspondent_merge import CorrespondentMerger

        counts = CorrespondentMerger(self).merge(target_id, source_id)
        return self.get_correspondent_or_404(target_id), counts

    def add_alias(self, correspondent_id: uuid.UUID, alias: str) -> Correspondent:
        correspondent = self.get_correspondent_or_404(correspondent_id)
        try:
            normalized = validate_correspondent_alias(alias)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        name_conflict = self._find_name_conflict(normalized)
        if name_conflict is not None and name_conflict.id != correspondent_id:
            raise ConflictError(
                "Dieser Alias oder Erkennungsname wird bereits als Korrespondentenname verwendet.",
                details={"alias": normalized},
            )

        conflicting_alias = self._find_alias_conflict(
            normalized,
            exclude_correspondent_id=correspondent_id,
        )
        if conflicting_alias is not None:
            raise ConflictError(
                "Dieser Alias oder Erkennungsname ist bereits einem anderen Korrespondenten zugeordnet.",
                details={"alias": normalized},
            )

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
            raise NotFoundError("Alias oder Erkennungsname wurde nicht gefunden.", details={"alias_id": str(alias_id)})
        auto_matchers = self.db.execute(
            select(CorrespondentMatcher).where(
                CorrespondentMatcher.correspondent_id == correspondent_id,
                CorrespondentMatcher.kind == "contains",
                func.lower(CorrespondentMatcher.pattern) == alias.alias.lower(),
            )
        ).scalars().all()
        for matcher in auto_matchers:
            self.db.delete(matcher)
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
            raise NotFoundError("Erkennungsregel wurde nicht gefunden.", details={"matcher_id": str(matcher_id)})
        self.db.delete(matcher)
        self.db.commit()
        return self.get_correspondent_or_404(correspondent_id)

    def get_profile(self, correspondent_id: uuid.UUID) -> CorrespondentProfileRead:
        correspondent = self.get_correspondent_or_404(correspondent_id)
        member_stmt = (
            select(Correspondent)
            .where(Correspondent.parent_id == correspondent_id)
            .order_by(func.lower(Correspondent.name).asc())
        )
        if self.owner_id is not None:
            member_stmt = member_stmt.where(Correspondent.owner_id == self.owner_id)
        members = self.db.execute(member_stmt).scalars().all()
        # Enkel (Personen der Organisationen einer Sammlung) zählen bei ihrem
        # Mitglied mit.
        grandchildren: dict[uuid.UUID, list[uuid.UUID]] = {}
        if members:
            grand_stmt = select(Correspondent.id, Correspondent.parent_id).where(
                Correspondent.parent_id.in_([member.id for member in members])
            )
            if self.owner_id is not None:
                grand_stmt = grand_stmt.where(Correspondent.owner_id == self.owner_id)
            for child_id, parent_id in self.db.execute(grand_stmt).all():
                grandchildren.setdefault(parent_id, []).append(child_id)
        ids = {correspondent_id, *(member.id for member in members), *(g for gs in grandchildren.values() for g in gs)}
        stats = self._document_stats(ids)

        def subtree_stats(member_id: uuid.UUID) -> tuple[int, date | None]:
            entries = [stats.get(cid, (0, None)) for cid in (member_id, *grandchildren.get(member_id, []))]
            dates = [last for _, last in entries if last is not None]
            return sum(count for count, _ in entries), max(dates) if dates else None

        scope = [Document.correspondent_id.in_(ids), Document.is_deleted.is_(False)]
        if self.owner_id is not None:
            scope.append(Document.owner_id == self.owner_id)
        effective_date = self._effective_date()
        first_date, last_date = self.db.execute(
            select(func.min(effective_date), func.max(effective_date)).where(*scope)
        ).one()

        amount_year = date.today().year
        amount_rows = self.db.execute(
            select(Document.currency, func.sum(Document.amount), func.count(Document.id))
            .where(*scope, Document.amount.is_not(None), func.extract("year", effective_date) == amount_year)
            .group_by(Document.currency)
            .order_by(func.count(Document.id).desc())
        ).all()

        activity_rows = self.db.execute(
            select(effective_date, Document.correspondent_id, Document.document_type)
            .where(*scope)
            .order_by(effective_date.asc())
        ).all()

        own_count, _ = stats.get(correspondent_id, (0, None))
        correspondent.usage_count = own_count
        correspondent.last_document_date = last_date
        return CorrespondentProfileRead(
            correspondent=CorrespondentRead.model_validate(correspondent, from_attributes=True),
            document_count=sum(count for count, _ in stats.values()),
            own_document_count=own_count,
            first_document_date=first_date,
            last_document_date=last_date,
            members=[
                CorrespondentProfileMember(
                    id=member.id,
                    name=member.name,
                    kind=member.kind,
                    document_count=subtree_stats(member.id)[0],
                    last_document_date=subtree_stats(member.id)[1],
                )
                for member in members
            ],
            amount_year=amount_year,
            amounts=[
                CorrespondentAmountSummary(currency=currency, total=total, count=int(count))
                for currency, total, count in amount_rows
            ],
            activity=[
                CorrespondentProfileActivity(document_date=day, correspondent_id=cid, document_type=doc_type)
                for day, cid, doc_type in activity_rows
                if day is not None
            ],
            relations=self.list_relations(correspondent_id),
        )

    # ── Verbindungen (Nachfolger, handelt für) ───────────────────────────────
    # Gespeichert gerichtet (source → target); nach außen als Rolle des anderen.
    _ROLE_TO_EDGE = {
        # role: (kind, ist der andere die Quelle?)
        "predecessor": ("successor", True),
        "successor": ("successor", False),
        "acts_for": ("acts_for", False),
        "agent": ("acts_for", True),
    }

    @staticmethod
    def _role_of(relation: CorrespondentRelation, correspondent_id: uuid.UUID) -> str:
        other_is_source = relation.target_id == correspondent_id
        if relation.kind == "successor":
            return "predecessor" if other_is_source else "successor"
        return "agent" if other_is_source else "acts_for"

    def _relations_of(self, correspondent_id: uuid.UUID) -> list[CorrespondentRelation]:
        stmt = select(CorrespondentRelation).where(
            (CorrespondentRelation.source_id == correspondent_id) | (CorrespondentRelation.target_id == correspondent_id)
        )
        if self.owner_id is not None:
            stmt = stmt.where(CorrespondentRelation.owner_id == self.owner_id)
        return list(self.db.execute(stmt.order_by(CorrespondentRelation.created_at.asc())).scalars().all())

    def list_relations(self, correspondent_id: uuid.UUID) -> list[CorrespondentRelationRead]:
        relations = self._relations_of(correspondent_id)
        if not relations:
            return []
        other_ids = {r.source_id if r.target_id == correspondent_id else r.target_id for r in relations}
        others = {
            c.id: c
            for c in self.db.execute(select(Correspondent).where(Correspondent.id.in_(other_ids))).scalars().all()
        }
        effective_date = self._effective_date()
        doc_stmt = (
            select(Document.correspondent_id, func.count(Document.id), func.min(effective_date), func.max(effective_date))
            .where(Document.correspondent_id.in_(other_ids), Document.is_deleted.is_(False))
            .group_by(Document.correspondent_id)
        )
        if self.owner_id is not None:
            doc_stmt = doc_stmt.where(Document.owner_id == self.owner_id)
        doc_stats = {cid: (int(n), first, last) for cid, n, first, last in self.db.execute(doc_stmt).all()}

        result = []
        for relation in relations:
            other_id = relation.source_id if relation.target_id == correspondent_id else relation.target_id
            other = others.get(other_id)
            if other is None:
                continue
            count, first, last = doc_stats.get(other_id, (0, None, None))
            result.append(
                CorrespondentRelationRead(
                    id=relation.id,
                    role=self._role_of(relation, correspondent_id),
                    other_id=other_id,
                    other_name=other.name,
                    other_kind=other.kind,
                    document_count=count,
                    first_document_date=first,
                    last_document_date=last,
                )
            )
        return result

    def _successor_chain(self, start_id: uuid.UUID) -> set[uuid.UUID]:
        """Alle Nachfolger ab ``start_id`` (für die Zyklusprüfung)."""
        seen: set[uuid.UUID] = set()
        current = start_id
        while current is not None and current not in seen:
            seen.add(current)
            current = self.db.execute(
                select(CorrespondentRelation.target_id).where(
                    CorrespondentRelation.source_id == current, CorrespondentRelation.kind == "successor"
                )
            ).scalar_one_or_none()
        return seen

    def add_relation(
        self, correspondent_id: uuid.UUID, payload: CorrespondentRelationCreateRequest
    ) -> CorrespondentRelationRead:
        correspondent = self.get_correspondent_or_404(correspondent_id)
        if payload.other_id == correspondent_id:
            raise BadRequestError("Ein Korrespondent kann nicht mit sich selbst verbunden werden.")
        other = self._get_owned(payload.other_id)
        if other is None:
            raise BadRequestError("Der ausgewählte Korrespondent wurde nicht gefunden.", details={"other_id": str(payload.other_id)})
        allowed_kinds = {"organization", "person"}
        if correspondent.kind not in allowed_kinds or other.kind not in allowed_kinds:
            raise BadRequestError("Nachfolge und Auftrag sind nur zwischen Personen und Organisationen möglich.")

        kind, other_is_source = self._ROLE_TO_EDGE[payload.role]
        source, target = (other, correspondent) if other_is_source else (correspondent, other)
        if kind == "successor":
            if self._get_successor_id(source.id) is not None:
                raise ConflictError(f"„{source.name}“ hat bereits einen Nachfolger.")
            if source.id in self._successor_chain(target.id):
                raise BadRequestError("Diese Verbindung würde einen Kreis aus Vorgängern ergeben.")
        exists = self.db.execute(
            select(CorrespondentRelation.id).where(
                CorrespondentRelation.source_id == source.id,
                CorrespondentRelation.target_id == target.id,
                CorrespondentRelation.kind == kind,
            )
        ).scalar_one_or_none()
        if exists is not None:
            raise ConflictError("Diese Verbindung besteht bereits.")

        relation = CorrespondentRelation(
            owner_id=correspondent.owner_id, kind=kind, source_id=source.id, target_id=target.id
        )
        self.db.add(relation)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Diese Verbindung besteht bereits.") from exc
            raise
        return next(r for r in self.list_relations(correspondent_id) if r.id == relation.id)

    def _get_successor_id(self, correspondent_id: uuid.UUID) -> uuid.UUID | None:
        return self.db.execute(
            select(CorrespondentRelation.target_id).where(
                CorrespondentRelation.source_id == correspondent_id, CorrespondentRelation.kind == "successor"
            )
        ).scalar_one_or_none()

    def delete_relation(self, correspondent_id: uuid.UUID, relation_id: uuid.UUID) -> None:
        self.get_correspondent_or_404(correspondent_id)
        relation = self.db.get(CorrespondentRelation, relation_id)
        if relation is None or correspondent_id not in (relation.source_id, relation.target_id) or (
            self.owner_id is not None and relation.owner_id != self.owner_id
        ):
            raise NotFoundError("Verbindung wurde nicht gefunden.", details={"relation_id": str(relation_id)})
        self.db.delete(relation)
        self.db.commit()

    def rollup_ids(self, correspondent_id: uuid.UUID) -> set[uuid.UUID]:
        """Korrespondent + alle untergeordneten Einträge (höchstens zwei Stufen).

        Sammlung → ihre Organisationen/Personen → deren Personen; Organisation
        → ihre Personen; Person → nur die eigene ID.
        """
        ids = {correspondent_id}
        frontier = {correspondent_id}
        for _ in range(2):
            child_stmt = select(Correspondent.id).where(Correspondent.parent_id.in_(frontier))
            if self.owner_id is not None:
                child_stmt = child_stmt.where(Correspondent.owner_id == self.owner_id)
            frontier = set(self.db.execute(child_stmt).scalars().all()) - ids
            if not frontier:
                break
            ids.update(frontier)
        return ids

    def correspondent_ids_exist(self, correspondent_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        if not correspondent_ids:
            return set()
        stmt = select(Correspondent.id).where(Correspondent.id.in_(correspondent_ids))
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        return set(self.db.execute(stmt).scalars().all())
