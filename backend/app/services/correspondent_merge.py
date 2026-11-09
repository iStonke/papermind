"""Zwei Korrespondenten zu einem zusammenführen.

Der Zieleintrag bleibt bestehen und übernimmt alles, was am Quelleintrag hängt:
Dokumente (auch im Papierkorb), zugeordnete Personen/Organisationen, Aliase,
Erkennungsregeln, Beziehungen und Verweise in Notizen. Der Name der Quelle wird
zum Alias des Ziels, damit künftige Dokumente mit dieser Schreibweise weiterhin
richtig erkannt werden. Danach wird die Quelle gelöscht – alles in einer
Transaktion.
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from app.core.errors import BadRequestError
from app.models.correspondent import Correspondent, CorrespondentAlias, CorrespondentMatcher, CorrespondentRelation
from app.models.document import Document
from app.models.note import Note, NoteLink
from app.services.utils import validate_correspondent_alias

if TYPE_CHECKING:
    from app.services.correspondents import CorrespondentService

logger = logging.getLogger("papermind.correspondents.merge")


@dataclass
class CorrespondentMergeCounts:
    documents: int = 0
    aliases: int = 0
    matchers: int = 0
    relations: int = 0
    members: int = 0
    notes: int = 0


def _rewrite_note_links(node: Any, source_id: str, target_id: str) -> bool:
    """wikiLink-Verweise auf die Quelle im Notiz-JSON auf das Ziel umbiegen."""
    changed = False
    if isinstance(node, dict):
        attrs = node.get("attrs")
        if (
            node.get("type") == "wikiLink"
            and isinstance(attrs, dict)
            and attrs.get("targetType") == "correspondent"
            and str(attrs.get("targetId")) == source_id
        ):
            attrs["targetId"] = target_id
            changed = True
        for child in node.get("content") or []:
            changed = _rewrite_note_links(child, source_id, target_id) or changed
    return changed


class CorrespondentMerger:
    def __init__(self, service: "CorrespondentService"):
        self.service = service
        self.db = service.db
        self.owner_id = service.owner_id

    def merge(self, target_id: uuid.UUID, source_id: uuid.UUID) -> CorrespondentMergeCounts:
        if target_id == source_id:
            raise BadRequestError("Ein Korrespondent kann nicht mit sich selbst zusammengeführt werden.")
        target = self.service.get_correspondent_or_404(target_id, for_update=True)
        source = self.service.get_correspondent_or_404(source_id, for_update=True)
        if target.kind and source.kind and target.kind != source.kind:
            raise BadRequestError(
                "Nur Einträge gleichen Typs können zusammengeführt werden. Ändere vorher den Typ eines der beiden.",
                details={"target_kind": target.kind, "source_kind": source.kind},
            )

        counts = CorrespondentMergeCounts()
        self._merge_fields(target, source)
        counts.members = self._move_members(target, source)
        counts.documents = self._move_documents(target, source)
        counts.aliases, counts.matchers = self._move_aliases_and_matchers(target, source)
        counts.relations = self._move_relations(target, source)
        counts.notes = self._rewrite_notes(target, source)

        source_name = source.name
        self.db.delete(source)
        self.db.flush()
        # Erst nach dem Löschen: Name der Quelle als Alias (sonst kollidiert er mit ihr selbst).
        if self._add_alias(target, source_name):
            counts.aliases += 1
        self.db.commit()
        logger.info(
            "correspondents merged target_id=%s source_id=%s documents=%s aliases=%s matchers=%s relations=%s members=%s notes=%s",
            target_id, source_id, counts.documents, counts.aliases, counts.matchers,
            counts.relations, counts.members, counts.notes,
        )
        return counts

    # -- Stammdaten ------------------------------------------------------------

    def _merge_fields(self, target: Correspondent, source: Correspondent) -> None:
        changed_structure = False
        if not target.kind and source.kind:
            target.kind = source.kind
            changed_structure = True
        if target.parent_id is None and source.parent_id is not None and source.parent_id != target.id:
            target.parent_id = source.parent_id
            changed_structure = True
        if changed_structure:
            self.service._validate_hierarchy(entity_id=target.id, kind=target.kind, parent_id=target.parent_id)
        if not target.short_name and source.short_name:
            target.short_name = source.short_name
        source_notes = (source.notes or "").strip()
        if source_notes and source_notes not in (target.notes or ""):
            prefix = f"{target.notes.rstrip()}\n\n" if (target.notes or "").strip() else ""
            target.notes = f"{prefix}Aus „{source.name}“:\n{source_notes}"

    def _move_members(self, target: Correspondent, source: Correspondent) -> int:
        stmt = update(Correspondent).where(Correspondent.parent_id == source.id, Correspondent.id != target.id)
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        moved = int(self.db.execute(stmt.values(parent_id=target.id)).rowcount or 0)
        if target.parent_id == source.id:
            target.parent_id = None
        return moved

    def _move_documents(self, target: Correspondent, source: Correspondent) -> int:
        # Alle Dokumente, auch im Papierkorb: sonst verlören sie beim Wiederherstellen ihren Absender.
        stmt = update(Document).where(Document.correspondent_id == source.id)
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        return int(self.db.execute(stmt.values(correspondent_id=target.id)).rowcount or 0)

    # -- Erkennung -------------------------------------------------------------

    def _move_aliases_and_matchers(self, target: Correspondent, source: Correspondent) -> tuple[int, int]:
        taken = {target.name.casefold(), *(alias.alias.casefold() for alias in target.aliases)}
        moved_aliases = 0
        for alias in list(source.aliases):
            key = alias.alias.casefold()
            if key in taken:
                self.db.delete(alias)
                continue
            taken.add(key)
            alias.correspondent_id = target.id
            moved_aliases += 1

        def matcher_key(matcher: CorrespondentMatcher) -> tuple[str, str, str]:
            return matcher.kind, matcher.pattern.casefold(), matcher.scope

        existing = {matcher_key(matcher) for matcher in target.matchers}
        moved_matchers = 0
        for matcher in list(source.matchers):
            key = matcher_key(matcher)
            if key in existing:
                self.db.delete(matcher)
                continue
            existing.add(key)
            matcher.correspondent_id = target.id
            moved_matchers += 1
        self.db.flush()
        self.db.expire(target, ["aliases", "matchers"])
        self.db.expire(source, ["aliases", "matchers"])
        return moved_aliases, moved_matchers

    def _add_alias(self, target: Correspondent, name: str) -> bool:
        try:
            alias = validate_correspondent_alias(name)
        except ValueError:
            return False
        if alias.casefold() == target.name.casefold():
            return False
        exists = self.db.execute(
            select(CorrespondentAlias.id).where(
                CorrespondentAlias.correspondent_id == target.id,
                func.lower(CorrespondentAlias.alias) == alias.lower(),
            )
        ).scalar_one_or_none()
        if exists is not None:
            return False
        self.db.add(CorrespondentAlias(correspondent_id=target.id, alias=alias))
        # Wie beim manuellen Alias: zusätzlich als contains-Regel für Dateiname/OCR.
        matcher_exists = self.db.execute(
            select(CorrespondentMatcher.id).where(
                CorrespondentMatcher.correspondent_id == target.id,
                CorrespondentMatcher.kind == "contains",
                func.lower(CorrespondentMatcher.pattern) == alias.lower(),
            )
        ).scalar_one_or_none()
        if matcher_exists is None:
            self.db.add(CorrespondentMatcher(correspondent_id=target.id, kind="contains", pattern=alias, scope="both", priority=100))
        return True

    # -- Beziehungen -----------------------------------------------------------

    def _move_relations(self, target: Correspondent, source: Correspondent) -> int:
        relations = self.db.execute(
            select(CorrespondentRelation).where(
                (CorrespondentRelation.source_id == source.id) | (CorrespondentRelation.target_id == source.id)
            )
        ).scalars().all()
        moved = 0
        for relation in relations:
            new_source = target.id if relation.source_id == source.id else relation.source_id
            new_target = target.id if relation.target_id == source.id else relation.target_id
            if new_source == new_target or self._relation_exists(new_source, new_target, relation.kind, relation.id):
                self.db.delete(relation)
                continue
            if relation.kind == "successor" and (
                self._has_other_successor(new_source, relation.id) or new_source in self._chain_without(new_target, relation.id)
            ):
                # Ein Eintrag hat höchstens einen Nachfolger, und Kreise sind verboten.
                self.db.delete(relation)
                continue
            relation.source_id = new_source
            relation.target_id = new_target
            self.db.flush()
            moved += 1
        self.db.flush()
        return moved

    def _relation_exists(self, source_id: uuid.UUID, target_id: uuid.UUID, kind: str, exclude_id: uuid.UUID) -> bool:
        return self.db.execute(
            select(CorrespondentRelation.id).where(
                CorrespondentRelation.source_id == source_id,
                CorrespondentRelation.target_id == target_id,
                CorrespondentRelation.kind == kind,
                CorrespondentRelation.id != exclude_id,
            )
        ).first() is not None

    def _has_other_successor(self, source_id: uuid.UUID, exclude_id: uuid.UUID) -> bool:
        return self.db.execute(
            select(CorrespondentRelation.id).where(
                CorrespondentRelation.source_id == source_id,
                CorrespondentRelation.kind == "successor",
                CorrespondentRelation.id != exclude_id,
            )
        ).first() is not None

    def _chain_without(self, start_id: uuid.UUID, exclude_id: uuid.UUID) -> set[uuid.UUID]:
        seen: set[uuid.UUID] = set()
        current: uuid.UUID | None = start_id
        while current is not None and current not in seen:
            seen.add(current)
            current = self.db.execute(
                select(CorrespondentRelation.target_id).where(
                    CorrespondentRelation.source_id == current,
                    CorrespondentRelation.kind == "successor",
                    CorrespondentRelation.id != exclude_id,
                )
            ).scalars().first()
        return seen

    # -- Notizen ---------------------------------------------------------------

    def _rewrite_notes(self, target: Correspondent, source: Correspondent) -> int:
        note_ids = self.db.execute(
            select(NoteLink.note_id).where(NoteLink.target_type == "correspondent", NoteLink.target_id == source.id).distinct()
        ).scalars().all()
        changed_notes = 0
        for note_id in note_ids:
            stmt = select(Note).where(Note.id == note_id)
            if self.owner_id is not None:
                stmt = stmt.where(Note.owner_id == self.owner_id)
            note = self.db.execute(stmt.with_for_update()).scalar_one_or_none()
            if note is None:
                continue
            body = copy.deepcopy(note.body_json or {})
            if _rewrite_note_links(body, str(source.id), str(target.id)):
                note.body_json = body
                # Offene Editoren sollen den geänderten Stand nicht stillschweigend überschreiben.
                note.revision = int(note.revision or 1) + 1
                changed_notes += 1
            already = self.db.execute(
                select(NoteLink.id).where(
                    NoteLink.note_id == note_id, NoteLink.target_type == "correspondent", NoteLink.target_id == target.id
                )
            ).first()
            links = update(NoteLink).where(
                NoteLink.note_id == note_id, NoteLink.target_type == "correspondent", NoteLink.target_id == source.id
            )
            if already is None:
                self.db.execute(links.values(target_id=target.id))
            else:
                self.db.query(NoteLink).filter(
                    NoteLink.note_id == note_id, NoteLink.target_type == "correspondent", NoteLink.target_id == source.id
                ).delete(synchronize_session=False)
        return changed_notes
