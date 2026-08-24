import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.note import Note, NoteLink
from app.schemas.notes import NoteCreateRequest, NoteListItem, NoteSearchScope, NoteUpdateRequest
from app.services.document_search import build_ts_query_expr, normalize_search_query

# Leeres ProseMirror-Dokument (ein Absatz) als Default für neue/kaputte Bodies.
EMPTY_DOC: dict[str, Any] = {"type": "doc", "content": [{"type": "paragraph"}]}

# Node-Attribute, die sichtbaren Text tragen (PaperMind-eigene Nodes aus M1).
# So landen Chip-Titel, Zitate & KI-Antworten mit im Volltext und in der Vorschau.
_NODE_TEXT_ATTRS: dict[str, tuple[str, ...]] = {
    "documentChip": ("title",),
    "wikiLink": ("label",),
    "ocrQuote": ("text",),
    "aiBlock": ("text",),
}

_WS = re.compile(r"\s+")
_PREVIEW_LEN = 200


def _search_preview(body_text: str, query: str | None) -> str:
    """Creates a compact contextual list snippet for note search hits."""
    text = (body_text or "").strip()
    if not text:
        return ""
    normalized_query = " ".join(str(query or "").split()).strip()
    if not normalized_query:
        return text[:_PREVIEW_LEN]

    lower_text = text.lower()
    match_positions = [
        lower_text.find(term.lower())
        for term in normalized_query.split()
        if term and lower_text.find(term.lower()) >= 0
    ]
    if not match_positions:
        return text[:_PREVIEW_LEN]

    first_match = min(match_positions)
    start = max(0, first_match - 64)
    end = min(len(text), start + _PREVIEW_LEN)
    if end - start < _PREVIEW_LEN:
        start = max(0, end - _PREVIEW_LEN)
    snippet = text[start:end].strip()
    return f"{'…' if start else ''}{snippet}{'…' if end < len(text) else ''}"


def prosemirror_to_text(node: Any) -> str:
    """Extrahiert den sichtbaren Text aus einem ProseMirror-JSON-Knoten."""
    if not isinstance(node, dict):
        return ""
    parts: list[str] = []
    if node.get("text"):
        parts.append(str(node["text"]))
    attrs = node.get("attrs") or {}
    for key in _NODE_TEXT_ATTRS.get(node.get("type", ""), ()):  # type: ignore[arg-type]
        val = attrs.get(key)
        if val:
            parts.append(str(val))
    for child in node.get("content") or []:
        child_text = prosemirror_to_text(child)
        if child_text:
            parts.append(child_text)
    return " ".join(parts)


def derive_body_text(body_json: Any) -> str:
    return _WS.sub(" ", prosemirror_to_text(body_json)).strip()


_VALID_TARGET_TYPES = {"document", "correspondent", "dossier", "note"}


def _parse_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def extract_note_links(body_json: Any) -> set[tuple[str, uuid.UUID]]:
    """Sammelt alle Objekt-Verweise einer Notiz aus body_json:
    root linkedDocument, wikiLink, documentChip, ocrQuote, aiBlock-Quellen."""
    links: set[tuple[str, uuid.UUID]] = set()
    if isinstance(body_json, dict):
        root_attrs = body_json.get("attrs")
        linked = root_attrs.get("linkedDocument") if isinstance(root_attrs, dict) else None
        if isinstance(linked, dict):
            did = _parse_uuid(linked.get("id"))
            if did:
                links.add(("document", did))

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        ntype = node.get("type")
        attrs = node.get("attrs") or {}
        if ntype == "wikiLink":
            tt = attrs.get("targetType")
            tid = _parse_uuid(attrs.get("targetId"))
            if tt in _VALID_TARGET_TYPES and tid:
                links.add((tt, tid))
        elif ntype in ("documentChip", "ocrQuote"):
            tid = _parse_uuid(attrs.get("docId"))
            if tid:
                links.add(("document", tid))
        elif ntype == "aiBlock":
            for src in attrs.get("sources") or []:
                if isinstance(src, dict):
                    tid = _parse_uuid(src.get("docId"))
                    if tid:
                        links.add(("document", tid))
        for child in node.get("content") or []:
            walk(child)

    walk(body_json)
    return links


class NoteService:
    """CRUD für owner-scoped Notizen. body_text wird serverseitig abgeleitet."""

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def _get(self, note_id: uuid.UUID, *, include_deleted: bool = False) -> Note | None:
        stmt = select(Note).where(Note.id == note_id, Note.owner_id == self.owner_id)
        if not include_deleted:
            stmt = stmt.where(Note.is_deleted.is_(False))
        return self.db.scalar(stmt)

    def list_notes(
        self,
        *,
        in_trash: bool = False,
        document_id: uuid.UUID | None = None,
        q: str | None = None,
        search_scope: NoteSearchScope = "all",
    ) -> list[NoteListItem]:
        stmt = (
            select(Note)
            .where(Note.owner_id == self.owner_id, Note.is_deleted.is_(in_trash))
        )
        if document_id is not None:
            # Notizen, die im ProseMirror-Wurzel-Attribut mit diesem Dokument
            # verknüpft sind (body_json.attrs.linkedDocument.id).
            stmt = stmt.where(
                Note.body_json["attrs"]["linkedDocument"]["id"].astext == str(document_id)
            )

        settings = get_settings()
        normalized_query = normalize_search_query(q, max_length=settings.search_query_max_length)
        if normalized_query:
            if search_scope == "title":
                escaped = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(func.coalesce(Note.title, "").ilike(f"%{escaped}%", escape="\\"))
            elif search_scope == "body":
                escaped = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(func.coalesce(Note.body_text, "").ilike(f"%{escaped}%", escape="\\"))
            else:
                ts_query = build_ts_query_expr(normalized_query, settings.fts_regconfig)
                stmt = stmt.where(Note.search_vector.op("@@")(ts_query))

        stmt = stmt.order_by((Note.deleted_at if in_trash else Note.updated_at).desc())
        rows = self.db.scalars(stmt).all()
        return [
            NoteListItem(
                id=n.id,
                title=n.title,
                preview=_search_preview(n.body_text or "", normalized_query),
                is_deleted=n.is_deleted,
                deleted_at=n.deleted_at,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in rows
        ]

    def get_note(self, note_id: uuid.UUID) -> Note | None:
        # Auch gelöschte Notizen liefern – für die read-only Papierkorb-Vorschau.
        return self._get(note_id, include_deleted=True)

    def _sync_links(self, note: Note) -> None:
        """Verweise der Notiz (note_link) aus body_json neu berechnen."""
        self.db.query(NoteLink).filter(NoteLink.note_id == note.id).delete(synchronize_session=False)
        for target_type, target_id in extract_note_links(note.body_json):
            # Selbstverweis überspringen.
            if target_type == "note" and target_id == note.id:
                continue
            self.db.add(NoteLink(note_id=note.id, target_type=target_type, target_id=target_id))

    def create_note(self, payload: NoteCreateRequest) -> Note:
        body_json = payload.body_json or EMPTY_DOC
        note = Note(
            owner_id=self.owner_id,
            title=payload.title or "",
            body_json=body_json,
            body_text=derive_body_text(body_json),
        )
        self.db.add(note)
        self.db.flush()  # note.id für note_link verfügbar machen
        self._sync_links(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def update_note(self, note_id: uuid.UUID, payload: NoteUpdateRequest) -> Note | None:
        note = self._get(note_id)
        if note is None:
            return None
        if payload.title is not None:
            note.title = payload.title
        if payload.body_json is not None:
            note.body_json = payload.body_json
            note.body_text = derive_body_text(payload.body_json)
            self._sync_links(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def list_references(self, target_type: str, target_id: uuid.UUID) -> list[NoteListItem]:
        """Notizen (nicht gelöscht), die auf das Zielobjekt verweisen (Rückverweise)."""
        rows = self.db.scalars(
            select(Note)
            .join(NoteLink, NoteLink.note_id == Note.id)
            .where(
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
                NoteLink.target_type == target_type,
                NoteLink.target_id == target_id,
            )
            .order_by(Note.updated_at.desc())
        ).all()
        return [
            NoteListItem(
                id=n.id,
                title=n.title,
                preview=(n.body_text or "")[:_PREVIEW_LEN],
                is_deleted=n.is_deleted,
                deleted_at=n.deleted_at,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in rows
        ]

    def trash_note(self, note_id: uuid.UUID) -> Note | None:
        note = self._get(note_id)
        if note is None:
            return None
        note.is_deleted = True
        note.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(note)
        return note

    def restore_note(self, note_id: uuid.UUID) -> Note | None:
        note = self._get(note_id, include_deleted=True)
        if note is None or not note.is_deleted:
            return None
        note.is_deleted = False
        note.deleted_at = None
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_note(self, note_id: uuid.UUID) -> bool:
        note = self._get(note_id, include_deleted=True)
        if note is None:
            return False
        self.db.delete(note)
        self.db.commit()
        return True

    def empty_trash(self) -> int:
        notes = list(
            self.db.scalars(
                select(Note).where(Note.owner_id == self.owner_id, Note.is_deleted.is_(True))
            ).all()
        )
        for note in notes:
            self.db.delete(note)
        if notes:
            self.db.commit()
        return len(notes)
