import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.document import Document
from app.models.note import Note
from app.models.note_learn_highlight import NoteLearnHighlight
from app.schemas.note_learn_highlights import NoteLearnHighlightCreate, NoteLearnHighlightUpdate


class NoteLearnHighlightService:
    """CRUD für Lernmarkierungen (Split-Ansicht Notiz↔Dokument).

    Eigentum wird zusätzlich zur RLS explizit über ``owner_id`` erzwungen (wie
    bei den Annotationen), damit es auch ohne RLS-Rolle greift. Markierungen von
    Notizen im Papierkorb bleiben gespeichert, werden aber nicht ausgeliefert –
    endgültig gelöschte Notizen nehmen sie per CASCADE mit.
    """

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    # ── intern ────────────────────────────────────────────────────────────────

    def _require_active_note(self, note_id: uuid.UUID) -> Note:
        note = self.db.execute(
            select(Note).where(
                Note.id == note_id,
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if note is None:
            raise NotFoundError("Note not found")
        return note

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

    def _require_owned_highlight(self, highlight_id: uuid.UUID) -> NoteLearnHighlight:
        highlight = self.db.execute(
            select(NoteLearnHighlight).where(
                NoteLearnHighlight.id == highlight_id,
                NoteLearnHighlight.owner_id == self.owner_id,
            )
        ).scalar_one_or_none()
        if highlight is None:
            raise NotFoundError("Learn highlight not found")
        return highlight

    # ── öffentlich ─────────────────────────────────────────────────────────────

    def list_for_note(
        self, note_id: uuid.UUID, document_id: uuid.UUID | None = None
    ) -> list[NoteLearnHighlight]:
        self._require_active_note(note_id)
        query = select(NoteLearnHighlight).where(
            NoteLearnHighlight.note_id == note_id,
            NoteLearnHighlight.owner_id == self.owner_id,
        )
        if document_id is not None:
            query = query.where(NoteLearnHighlight.document_id == document_id)
        query = query.order_by(NoteLearnHighlight.page.asc(), NoteLearnHighlight.created_at.asc())
        return list(self.db.execute(query).scalars())

    def list_for_document(self, document_id: uuid.UUID) -> list[NoteLearnHighlight]:
        """Gesamtübersicht: alle Lernmarkierungen aller (aktiven) Notizen eines
        Dokuments, mit transientem ``note_title`` für die Anzeige."""
        self._require_owned_document(document_id)
        rows = self.db.execute(
            select(NoteLearnHighlight, Note.title)
            .join(Note, Note.id == NoteLearnHighlight.note_id)
            .where(
                NoteLearnHighlight.document_id == document_id,
                NoteLearnHighlight.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
            )
            .order_by(NoteLearnHighlight.page.asc(), NoteLearnHighlight.created_at.asc())
        ).all()
        items = []
        for highlight, note_title in rows:
            highlight.note_title = note_title or ""
            items.append(highlight)
        return items

    def create(self, note_id: uuid.UUID, payload: NoteLearnHighlightCreate) -> NoteLearnHighlight:
        self._require_active_note(note_id)
        self._require_owned_document(payload.document_id)
        highlight = NoteLearnHighlight(
            owner_id=self.owner_id,
            note_id=note_id,
            document_id=payload.document_id,
            page=payload.page,
            color=payload.color,
            rects=[rect.model_dump() for rect in payload.rects],
            quote=(payload.quote or "").strip() or None,
        )
        self.db.add(highlight)
        self.db.commit()
        self.db.refresh(highlight)
        return highlight

    def update(self, highlight_id: uuid.UUID, payload: NoteLearnHighlightUpdate) -> NoteLearnHighlight:
        highlight = self._require_owned_highlight(highlight_id)
        highlight.color = payload.color
        self.db.commit()
        self.db.refresh(highlight)
        return highlight

    def delete(self, highlight_id: uuid.UUID) -> None:
        highlight = self._require_owned_highlight(highlight_id)
        self.db.delete(highlight)
        self.db.commit()
