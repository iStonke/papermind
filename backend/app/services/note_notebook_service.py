import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.note import Note
from app.models.note_notebook import NoteNotebook
from app.schemas.notes import (
    NotebookCreateRequest,
    NotebookRead,
    NotebookUpdateRequest,
)


class NoteNotebookService:
    """CRUD und Zuordnung für Notizbücher (flache, owner-scoped Ablageebene)."""

    def __init__(self, db: Session, owner_id: uuid.UUID) -> None:
        self.db = db
        self.owner_id = owner_id

    # --- Lesen ---------------------------------------------------------------
    def _note_counts(self) -> dict[uuid.UUID, int]:
        """Anzahl nicht gelöschter, nicht-Vorlage-Notizen je Notizbuch."""
        rows = self.db.execute(
            select(Note.notebook_id, func.count())
            .where(
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
                Note.is_template.is_(False),
                Note.notebook_id.is_not(None),
            )
            .group_by(Note.notebook_id)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    def list_notebooks(self) -> list[NotebookRead]:
        rows = self.db.scalars(
            select(NoteNotebook)
            .where(NoteNotebook.owner_id == self.owner_id)
            .order_by(NoteNotebook.position, func.lower(NoteNotebook.name))
        ).all()
        counts = self._note_counts()
        return [
            NotebookRead(
                id=nb.id,
                name=nb.name,
                color=nb.color,
                position=nb.position,
                note_count=counts.get(nb.id, 0),
                created_at=nb.created_at,
                updated_at=nb.updated_at,
            )
            for nb in rows
        ]

    def _get(self, notebook_id: uuid.UUID) -> NoteNotebook:
        nb = self.db.scalar(
            select(NoteNotebook).where(
                NoteNotebook.id == notebook_id, NoteNotebook.owner_id == self.owner_id
            )
        )
        if nb is None:
            raise NotFoundError("Notizbuch nicht gefunden", details={"notebook_id": str(notebook_id)})
        return nb

    # --- Schreiben -----------------------------------------------------------
    def create_notebook(self, payload: NotebookCreateRequest) -> NotebookRead:
        name = payload.name.strip()
        if not name:
            raise ConflictError("Der Name des Notizbuchs darf nicht leer sein.")
        # Neues Buch ans Ende (höchste Position + 1).
        max_pos = self.db.scalar(
            select(func.coalesce(func.max(NoteNotebook.position), -1)).where(
                NoteNotebook.owner_id == self.owner_id
            )
        )
        nb = NoteNotebook(
            owner_id=self.owner_id,
            name=name,
            color=(payload.color or None),
            position=int(max_pos) + 1,
        )
        self.db.add(nb)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Ein Notizbuch mit diesem Namen existiert bereits.",
                details={"name": name},
            ) from exc
        self.db.refresh(nb)
        return NotebookRead(
            id=nb.id,
            name=nb.name,
            color=nb.color,
            position=nb.position,
            note_count=0,
            created_at=nb.created_at,
            updated_at=nb.updated_at,
        )

    def update_notebook(self, notebook_id: uuid.UUID, payload: NotebookUpdateRequest) -> NotebookRead:
        nb = self._get(notebook_id)
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ConflictError("Der Name des Notizbuchs darf nicht leer sein.")
            nb.name = name
        if "color" in payload.model_fields_set:
            nb.color = payload.color or None
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Ein Notizbuch mit diesem Namen existiert bereits.",
                details={"name": nb.name},
            ) from exc
        self.db.refresh(nb)
        counts = self._note_counts()
        return NotebookRead(
            id=nb.id,
            name=nb.name,
            color=nb.color,
            position=nb.position,
            note_count=counts.get(nb.id, 0),
            created_at=nb.created_at,
            updated_at=nb.updated_at,
        )

    def delete_notebook(self, notebook_id: uuid.UUID) -> None:
        """Löscht das Notizbuch. Enthaltene Notizen bleiben erhalten und rutschen
        durch ``ON DELETE SET NULL`` nach „Ohne Notizbuch"."""
        nb = self._get(notebook_id)
        self.db.delete(nb)
        self.db.commit()

    def move_notes(self, ids: list[uuid.UUID], notebook_id: uuid.UUID | None) -> int:
        """Verschiebt mehrere Notizen in ein Notizbuch (oder ``None`` = heraus).

        Vorlagen und gelöschte Notizen werden übersprungen. Gibt die Zahl
        tatsächlich verschobener Notizen zurück."""
        if notebook_id is not None:
            self._get(notebook_id)  # Eigentümerschaft/Existenz sicherstellen
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
            if note.notebook_id != notebook_id:
                note.notebook_id = notebook_id
                affected += 1
        if affected:
            self.db.commit()
        return affected

    def reorder_notebooks(self, ordered_ids: list[uuid.UUID]) -> list[NotebookRead]:
        """Setzt die Anzeige-Reihenfolge (``position``) gemäß der übergebenen
        ID-Liste. Unbekannte/fremde IDs werden ignoriert; nicht genannte
        Notizbücher behalten ihre relative Reihenfolge und rutschen ans Ende."""
        owned = {
            nb.id: nb
            for nb in self.db.scalars(
                select(NoteNotebook).where(NoteNotebook.owner_id == self.owner_id)
            ).all()
        }
        seen: set[uuid.UUID] = set()
        pos = 0
        for nid in ordered_ids:
            nb = owned.get(nid)
            if nb is None or nid in seen:
                continue
            seen.add(nid)
            nb.position = pos
            pos += 1
        # Nicht genannte hinten anhängen (stabile Reihenfolge nach altem position).
        for nb in sorted(
            (nb for nid, nb in owned.items() if nid not in seen),
            key=lambda n: n.position,
        ):
            nb.position = pos
            pos += 1
        self.db.commit()
        return self.list_notebooks()
