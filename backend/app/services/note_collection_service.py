import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.note import Note
from app.models.note_collection import NoteCollection
from app.models.note_notebook import NoteNotebook
from app.schemas.notes import (
    CollectionCreateRequest,
    CollectionRead,
    CollectionUpdateRequest,
)

DEFAULT_COLLECTION_NAME = "Allgemein"


class NoteCollectionService:
    """CRUD und Partition-Logik für Sammlungen (oberste Notizen-Ebene).

    Eine Sammlung ist eine harte Partition: echte Notizen liegen in genau einer,
    Vorlagen bewusst in keiner (global). ``note.collection_id`` ist die Wahrheit,
    ``note_notebook.collection_id`` spiegelt sie.
    """

    def __init__(self, db: Session, owner_id: uuid.UUID) -> None:
        self.db = db
        self.owner_id = owner_id

    # --- Lesen ---------------------------------------------------------------
    def _note_counts(self) -> dict[uuid.UUID, int]:
        """Anzahl nicht gelöschter, nicht-Vorlage-Notizen je Sammlung."""
        rows = self.db.execute(
            select(Note.collection_id, func.count())
            .where(
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
                Note.is_template.is_(False),
                Note.collection_id.is_not(None),
            )
            .group_by(Note.collection_id)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    def _read(self, coll: NoteCollection, counts: dict[uuid.UUID, int] | None = None) -> CollectionRead:
        counts = counts if counts is not None else self._note_counts()
        return CollectionRead(
            id=coll.id,
            name=coll.name,
            color=coll.color,
            position=coll.position,
            note_count=counts.get(coll.id, 0),
            created_at=coll.created_at,
            updated_at=coll.updated_at,
        )

    def _all(self) -> list[NoteCollection]:
        return list(
            self.db.scalars(
                select(NoteCollection)
                .where(NoteCollection.owner_id == self.owner_id)
                .order_by(NoteCollection.position, func.lower(NoteCollection.name))
            ).all()
        )

    def list_collections(self) -> list[CollectionRead]:
        rows = self._all()
        if not rows:
            # Neue/leere Owner erhalten ihre erste Sammlung lazy (nicht per
            # Migration): so ist die Oberfläche nie ohne aktive Sammlung.
            rows = [self._create_default()]
        counts = self._note_counts()
        return [self._read(c, counts) for c in rows]

    def _get(self, collection_id: uuid.UUID) -> NoteCollection:
        coll = self.db.scalar(
            select(NoteCollection).where(
                NoteCollection.id == collection_id, NoteCollection.owner_id == self.owner_id
            )
        )
        if coll is None:
            raise NotFoundError("Sammlung nicht gefunden", details={"collection_id": str(collection_id)})
        return coll

    # --- Standardsammlung ----------------------------------------------------
    def _create_default(self) -> NoteCollection:
        coll = NoteCollection(owner_id=self.owner_id, name=DEFAULT_COLLECTION_NAME, position=0)
        self.db.add(coll)
        try:
            self.db.commit()
        except IntegrityError:
            # Rennen mit paralleler Anlage: vorhandene „Allgemein" nutzen.
            self.db.rollback()
            coll = self.db.scalar(
                select(NoteCollection).where(
                    NoteCollection.owner_id == self.owner_id,
                    NoteCollection.name == DEFAULT_COLLECTION_NAME,
                )
            )
            if coll is None:  # pragma: no cover - defensiv
                raise
        else:
            self.db.refresh(coll)
        return coll

    def ensure_default_id(self) -> uuid.UUID:
        """ID einer nutzbaren Sammlung – erste vorhandene, sonst frisch angelegte.

        Genutzt von ``NoteService``/``NoteNotebookService``, wenn ein Client keine
        Sammlung mitschickt, damit die harte Partition trotzdem erfüllt ist.
        """
        existing = self.db.scalar(
            select(NoteCollection.id)
            .where(NoteCollection.owner_id == self.owner_id)
            .order_by(NoteCollection.position, func.lower(NoteCollection.name))
            .limit(1)
        )
        if existing is not None:
            return existing
        return self._create_default().id

    def resolve_id(self, collection_id: uuid.UUID | None) -> uuid.UUID:
        """Validiert eine übergebene Sammlung (Eigentümerschaft) oder liefert die
        Standardsammlung, wenn ``None``."""
        if collection_id is None:
            return self.ensure_default_id()
        self._get(collection_id)
        return collection_id

    # --- Schreiben -----------------------------------------------------------
    def create_collection(self, payload: CollectionCreateRequest) -> CollectionRead:
        name = payload.name.strip()
        if not name:
            raise ConflictError("Der Name der Sammlung darf nicht leer sein.")
        max_pos = self.db.scalar(
            select(func.coalesce(func.max(NoteCollection.position), -1)).where(
                NoteCollection.owner_id == self.owner_id
            )
        )
        coll = NoteCollection(
            owner_id=self.owner_id,
            name=name,
            color=(payload.color or None),
            position=int(max_pos) + 1,
        )
        self.db.add(coll)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Eine Sammlung mit diesem Namen existiert bereits.",
                details={"name": name},
            ) from exc
        self.db.refresh(coll)
        return self._read(coll, counts={})

    def update_collection(self, collection_id: uuid.UUID, payload: CollectionUpdateRequest) -> CollectionRead:
        coll = self._get(collection_id)
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ConflictError("Der Name der Sammlung darf nicht leer sein.")
            coll.name = name
        if "color" in payload.model_fields_set:
            coll.color = payload.color or None
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Eine Sammlung mit diesem Namen existiert bereits.",
                details={"name": coll.name},
            ) from exc
        self.db.refresh(coll)
        return self._read(coll)

    def delete_collection(self, collection_id: uuid.UUID, reassign_to: uuid.UUID | None = None) -> None:
        """Löscht eine Sammlung. Zwei Wächter für die harte Partition:

        * Die **letzte** Sammlung ist nicht löschbar (es muss immer eine geben).
        * Eine **nicht-leere** Sammlung nur mit Ziel: Notizen + Notizbücher werden
          zuvor nach ``reassign_to`` umgehängt (``ON DELETE RESTRICT`` verhindert
          sonst verwaiste Zeilen).
        """
        coll = self._get(collection_id)
        total = self.db.scalar(
            select(func.count()).select_from(NoteCollection).where(
                NoteCollection.owner_id == self.owner_id
            )
        )
        if int(total or 0) <= 1:
            raise ConflictError("Die letzte Sammlung kann nicht gelöscht werden.")

        notebook_count = self.db.scalar(
            select(func.count()).select_from(NoteNotebook).where(
                NoteNotebook.owner_id == self.owner_id, NoteNotebook.collection_id == collection_id
            )
        )
        note_count = self.db.scalar(
            select(func.count()).select_from(Note).where(
                Note.owner_id == self.owner_id, Note.collection_id == collection_id
            )
        )
        if int(notebook_count or 0) or int(note_count or 0):
            if reassign_to is None:
                raise ConflictError(
                    "Die Sammlung ist nicht leer – bitte eine Zielsammlung zum Umhängen angeben.",
                    details={"notebooks": int(notebook_count or 0), "notes": int(note_count or 0)},
                )
            if reassign_to == collection_id:
                raise ConflictError("Ziel- und Quellsammlung müssen verschieden sein.")
            target = self._get(reassign_to)
            self.db.execute(
                update(NoteNotebook)
                .where(NoteNotebook.owner_id == self.owner_id, NoteNotebook.collection_id == collection_id)
                .values(collection_id=target.id)
            )
            self.db.execute(
                update(Note)
                .where(Note.owner_id == self.owner_id, Note.collection_id == collection_id)
                .values(collection_id=target.id)
            )

        self.db.delete(coll)
        self.db.commit()

    def move_notes(self, ids: list[uuid.UUID], collection_id: uuid.UUID) -> int:
        """Verschiebt Notizen in eine andere Sammlung und **koppelt das Notizbuch
        ab** (das gehörte zur alten Sammlung). Vorlagen und gelöschte Notizen
        werden übersprungen. Gibt die Zahl tatsächlich verschobener Notizen zurück."""
        self._get(collection_id)  # Eigentümerschaft/Existenz sicherstellen
        rows = list(
            self.db.scalars(
                select(Note).where(
                    Note.owner_id == self.owner_id,
                    Note.id.in_(ids),
                    Note.is_template.is_(False),
                    Note.is_deleted.is_(False),
                )
            ).all()
        )
        affected = 0
        for note in rows:
            if note.collection_id != collection_id:
                note.collection_id = collection_id
                note.notebook_id = None
                affected += 1
        if affected:
            self.db.commit()
        return affected

    def reorder_collections(self, ordered_ids: list[uuid.UUID]) -> list[CollectionRead]:
        """Setzt die Anzeige-Reihenfolge (``position``). Unbekannte/fremde IDs
        werden ignoriert; nicht genannte Sammlungen rutschen stabil ans Ende."""
        owned = {c.id: c for c in self._all()}
        seen: set[uuid.UUID] = set()
        pos = 0
        for cid in ordered_ids:
            coll = owned.get(cid)
            if coll is None or cid in seen:
                continue
            seen.add(cid)
            coll.position = pos
            pos += 1
        for coll in sorted(
            (c for cid, c in owned.items() if cid not in seen), key=lambda c: c.position
        ):
            coll.position = pos
            pos += 1
        self.db.commit()
        return self.list_collections()
