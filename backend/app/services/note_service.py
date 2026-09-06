import copy
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.models.note import Note, NoteLink, NoteRevision, NoteTask
from app.models.note_image import NoteImage
from app.models.note_notebook import NoteNotebook
from app.models.note_tag import note_tags
from app.models.tag import Tag
from app.schemas.notes import (
    NoteCreateRequest,
    NoteHistoryReason,
    NoteListItem,
    NoteRevisionListItem,
    NoteRevisionListResponse,
    NoteSearchScope,
    NoteTagRef,
    NoteUpdateRequest,
)
from app.services.document_search import build_ts_query_expr, normalize_search_query
from app.services.note_images import NoteImageService, NoteImageStorage

# Leeres ProseMirror-Dokument (ein Absatz) als Default für neue/kaputte Bodies.
EMPTY_DOC: dict[str, Any] = {"type": "doc", "content": [{"type": "paragraph"}]}

# Node-Attribute, die sichtbaren Text tragen (PaperMind-eigene Nodes aus M1).
# So landen Chip-Titel, Zitate & KI-Antworten mit im Volltext und in der Vorschau.
_NODE_TEXT_ATTRS: dict[str, tuple[str, ...]] = {
    "documentChip": ("title",),
    "wikiLink": ("label",),
    "ocrQuote": ("text",),
    "aiBlock": ("text",),
    "image": ("caption", "alt", "title"),
}

_WS = re.compile(r"\s+")
_PREVIEW_LEN = 200
_NOTE_HISTORY_LIMIT = 100
_AUTOSAVE_HISTORY_WINDOW = timedelta(minutes=5)


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


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _tag_refs(note: Note) -> list[NoteTagRef]:
    """Tags einer Notiz als schlanke Referenzen (id, name), alphabetisch."""
    tags = getattr(note, "tags", None) or []
    return [NoteTagRef(id=t.id, name=t.name) for t in sorted(tags, key=lambda t: t.name.lower())]


def extract_note_tasks(body_json: Any) -> list[dict[str, Any]]:
    """Sammelt Aufgaben (taskItem) einer Notiz in Dokumentreihenfolge.

    Liefert je Aufgabe {text, done, due_date, position}. ``text`` ist der
    sichtbare Aufgabentext, ``due_date`` das optionale Fälligkeitsdatum aus dem
    ``dueDate``-Attribut (M6 Teil B).
    """
    tasks: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "taskItem":
            attrs = node.get("attrs") or {}
            text = _WS.sub(" ", prosemirror_to_text(node)).strip()
            tasks.append({
                "text": text[:2000],
                "done": bool(attrs.get("checked")),
                "due_date": _parse_date(attrs.get("dueDate")),
                "position": len(tasks),
            })
        for child in node.get("content") or []:
            walk(child)

    walk(body_json)
    return tasks


class NoteService:
    """CRUD für owner-scoped Notizen. body_text wird serverseitig abgeleitet."""

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def _get(
        self,
        note_id: uuid.UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Note | None:
        stmt = select(Note).where(Note.id == note_id, Note.owner_id == self.owner_id)
        if not include_deleted:
            stmt = stmt.where(Note.is_deleted.is_(False))
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def _link_counts(self, note_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Aus- und eingehende Verweise je Notiz (für Facette/Chip „Verwaist").

        Eingehende Verweise zählen nur, wenn die verweisende Notiz demselben
        Eigentümer gehört und nicht im Papierkorb liegt (Daten-Isolation).
        """
        counts: dict[uuid.UUID, int] = {nid: 0 for nid in note_ids}
        if not note_ids:
            return counts
        outgoing = self.db.execute(
            select(NoteLink.note_id, func.count())
            .where(NoteLink.note_id.in_(note_ids))
            .group_by(NoteLink.note_id)
        ).all()
        for nid, cnt in outgoing:
            counts[nid] = counts.get(nid, 0) + cnt
        incoming = self.db.execute(
            select(NoteLink.target_id, func.count())
            .join(Note, Note.id == NoteLink.note_id)
            .where(
                NoteLink.target_type == "note",
                NoteLink.target_id.in_(note_ids),
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
            )
            .group_by(NoteLink.target_id)
        ).all()
        for tid, cnt in incoming:
            counts[tid] = counts.get(tid, 0) + cnt
        return counts

    def list_notes(
        self,
        *,
        in_trash: bool = False,
        document_id: uuid.UUID | None = None,
        dossier_id: uuid.UUID | None = None,
        tag_id: uuid.UUID | None = None,
        notebook_id: uuid.UUID | None = None,
        no_notebook: bool = False,
        favorites_only: bool = False,
        templates: bool = False,
        q: str | None = None,
        search_scope: NoteSearchScope = "all",
    ) -> list[NoteListItem]:
        if dossier_id is not None:
            # Dossiers werden ausschließlich über Wiki-Verweise (wikiLink) im
            # Notiztext referenziert; diese liegen denormalisiert in note_link.
            return self.list_references("dossier", dossier_id)

        stmt = (
            select(Note)
            .where(
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(in_trash),
                Note.is_template.is_(templates),
            )
        )
        if tag_id is not None:
            stmt = stmt.where(
                select(note_tags.c.note_id)
                .where(note_tags.c.note_id == Note.id, note_tags.c.tag_id == tag_id)
                .exists()
            )
        # Notizbuch-Facette: konkretes Buch oder „Ohne Notizbuch" (no_notebook).
        # ``notebook_id`` hat Vorrang; beide zusammen sind widersprüchlich, dann
        # gewinnt das konkrete Buch.
        if notebook_id is not None:
            stmt = stmt.where(Note.notebook_id == notebook_id)
        elif no_notebook:
            stmt = stmt.where(Note.notebook_id.is_(None))
        if favorites_only:
            stmt = stmt.where(Note.is_favorite.is_(True))
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
                escaped = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                tag_match = (
                    select(note_tags.c.note_id)
                    .join(Tag, Tag.id == note_tags.c.tag_id)
                    .where(
                        note_tags.c.note_id == Note.id,
                        Tag.owner_id == self.owner_id,
                        Tag.name.ilike(f"%{escaped}%", escape="\\"),
                    )
                    .exists()
                )
                notebook_match = (
                    select(NoteNotebook.id)
                    .where(
                        NoteNotebook.id == Note.notebook_id,
                        NoteNotebook.owner_id == self.owner_id,
                        NoteNotebook.name.ilike(f"%{escaped}%", escape="\\"),
                    )
                    .exists()
                )
                stmt = stmt.where(or_(Note.search_vector.op("@@")(ts_query), tag_match, notebook_match))

        stmt = stmt.order_by((Note.deleted_at if in_trash else Note.updated_at).desc())
        rows = self.db.scalars(stmt).all()
        link_counts = self._link_counts([n.id for n in rows])
        return [
            NoteListItem(
                id=n.id,
                title=n.title,
                preview=_search_preview(n.body_text or "", normalized_query),
                is_template=n.is_template,
                is_deleted=n.is_deleted,
                deleted_at=n.deleted_at,
                link_count=link_counts.get(n.id, 0),
                notebook_id=n.notebook_id,
                is_favorite=n.is_favorite,
                tags=_tag_refs(n),
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

    def _sync_tasks(self, note: Note) -> None:
        """Aufgaben der Notiz (note_task) aus body_json neu berechnen."""
        self.db.query(NoteTask).filter(NoteTask.note_id == note.id).delete(synchronize_session=False)
        for task in extract_note_tasks(note.body_json):
            self.db.add(NoteTask(note_id=note.id, **task))

    def _latest_revision(self, note_id: uuid.UUID, *, for_update: bool = False) -> NoteRevision | None:
        stmt = (
            select(NoteRevision)
            .where(NoteRevision.note_id == note_id, NoteRevision.owner_id == self.owner_id)
            .order_by(NoteRevision.updated_at.desc(), NoteRevision.created_at.desc())
            .limit(1)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    @staticmethod
    def _revision_matches_note(revision: NoteRevision, note: Note) -> bool:
        return revision.title == (note.title or "") and revision.body_json == (note.body_json or EMPTY_DOC)

    def _record_revision(
        self,
        note: Note,
        *,
        reason: NoteHistoryReason = "autosave",
        force_new: bool = False,
    ) -> NoteRevision:
        """Aktuellen Stand ablegen; eng aufeinanderfolgende Autosaves bündeln."""
        now = datetime.now(timezone.utc)
        latest = self._latest_revision(note.id, for_update=True)
        latest_updated_at = latest.updated_at if latest else None
        if latest_updated_at is not None and latest_updated_at.tzinfo is None:
            latest_updated_at = latest_updated_at.replace(tzinfo=timezone.utc)
        can_group = (
            not force_new
            and reason == "autosave"
            and latest is not None
            and latest.reason == "autosave"
            and latest_updated_at is not None
            and latest_updated_at >= now - _AUTOSAVE_HISTORY_WINDOW
        )
        if can_group:
            latest.note_revision = int(note.revision or 1)
            latest.title = note.title or ""
            latest.body_json = copy.deepcopy(note.body_json) or EMPTY_DOC
            latest.body_text = note.body_text or ""
            latest.updated_at = now
            return latest

        revision = NoteRevision(
            note_id=note.id,
            owner_id=self.owner_id,
            note_revision=int(note.revision or 1),
            reason=reason,
            title=note.title or "",
            body_json=copy.deepcopy(note.body_json) or EMPTY_DOC,
            body_text=note.body_text or "",
            created_at=now,
            updated_at=now,
        )
        self.db.add(revision)
        return revision

    def _checkpoint_revision(self, note: Note, reason: NoteHistoryReason) -> NoteRevision:
        """Autosave-Gruppe abschließen, ohne identische Doppelstände anzulegen."""
        latest = self._latest_revision(note.id, for_update=True)
        if latest is not None and self._revision_matches_note(latest, note):
            if latest.reason == "autosave":
                latest.reason = reason
                latest.updated_at = datetime.now(timezone.utc)
            return latest
        return self._record_revision(note, reason=reason, force_new=True)

    def _resolve_notebook_id(self, notebook_id: uuid.UUID | None) -> uuid.UUID | None:
        """Validiert, dass das Notizbuch dem Eigentümer gehört.

        ``None`` bleibt ``None`` (Ohne Notizbuch). Ein fremdes/unbekanntes Buch
        führt zu ``NotFoundError`` statt eines FK-Fehlers auf Commit-Ebene.
        """
        if notebook_id is None:
            return None
        exists = self.db.scalar(
            select(NoteNotebook.id).where(
                NoteNotebook.id == notebook_id, NoteNotebook.owner_id == self.owner_id
            )
        )
        if exists is None:
            raise NotFoundError("Notizbuch nicht gefunden", details={"notebook_id": str(notebook_id)})
        return notebook_id

    def create_note(self, payload: NoteCreateRequest) -> Note:
        body_json = payload.body_json or EMPTY_DOC
        note = Note(
            owner_id=self.owner_id,
            title=payload.title or "",
            body_json=body_json,
            body_text=derive_body_text(body_json),
            is_template=payload.is_template,
            # Vorlagen liegen bewusst in keinem Notizbuch.
            notebook_id=None if payload.is_template else self._resolve_notebook_id(payload.notebook_id),
        )
        self.db.add(note)
        self.db.flush()  # note.id für note_link/note_task verfügbar machen
        # Vorlagen sind inerte Gerüste – sie erzeugen keine Verweise/Aufgaben.
        if not note.is_template:
            self._sync_links(note)
            self._sync_tasks(note)
            self._record_revision(note, reason="created", force_new=True)
        self.db.commit()
        self.db.refresh(note)
        return note

    # --- Vorlagen (M6) -------------------------------------------------------
    def list_templates(self) -> list[NoteListItem]:
        """Alle Vorlagen des Eigentümers (nicht gelöscht), neueste zuerst."""
        rows = self.db.scalars(
            select(Note)
            .where(
                Note.owner_id == self.owner_id,
                Note.is_deleted.is_(False),
                Note.is_template.is_(True),
            )
            .order_by(Note.updated_at.desc())
        ).all()
        return [
            NoteListItem(
                id=n.id,
                title=n.title,
                preview=_search_preview(n.body_text or "", None),
                is_template=True,
                is_deleted=n.is_deleted,
                deleted_at=n.deleted_at,
                tags=_tag_refs(n),
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in rows
        ]

    def create_from_template(self, template_id: uuid.UUID) -> Note | None:
        """Neue reguläre Notiz aus einer Vorlage (body_json kopiert)."""
        template = self._get(template_id)
        if template is None or not template.is_template:
            return None
        body_json = copy.deepcopy(template.body_json) or EMPTY_DOC
        note = Note(
            owner_id=self.owner_id,
            title=template.title or "",
            body_json=body_json,
            body_text=derive_body_text(body_json),
            is_template=False,
        )
        self.db.add(note)
        self.db.flush()
        image_service = NoteImageService(self.db, self.owner_id)
        body_json, cloned_file_keys = image_service.clone_body_images(
            body_json,
            source_note_id=template.id,
            target_note_id=note.id,
        )
        note.body_json = body_json
        note.body_text = derive_body_text(body_json)
        self._sync_links(note)
        self._sync_tasks(note)
        self._record_revision(note, reason="created", force_new=True)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            for file_key in cloned_file_keys:
                image_service.storage.cleanup(file_key)
            raise
        self.db.refresh(note)
        return note

    def save_as_template(self, note_id: uuid.UUID, title: str = "") -> Note | None:
        """Aus einer bestehenden Notiz eine neue Vorlage ableiten.

        Die Bindung an ein konkretes Dokument (Wurzel-Attribut ``linkedDocument``)
        wird entfernt, damit die Vorlage dokument-unabhängig ist.
        """
        source = self._get(note_id)
        if source is None:
            return None
        body_json = copy.deepcopy(source.body_json) or EMPTY_DOC
        attrs = body_json.get("attrs")
        if isinstance(attrs, dict):
            attrs.pop("linkedDocument", None)
        template = Note(
            owner_id=self.owner_id,
            title=(title or source.title or "").strip(),
            body_json=body_json,
            body_text=derive_body_text(body_json),
            is_template=True,
        )
        self.db.add(template)
        self.db.flush()
        image_service = NoteImageService(self.db, self.owner_id)
        body_json, cloned_file_keys = image_service.clone_body_images(
            body_json,
            source_note_id=source.id,
            target_note_id=template.id,
        )
        template.body_json = body_json
        template.body_text = derive_body_text(body_json)
        # Vorlage erzeugt bewusst keine note_link-Zeilen.
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            for file_key in cloned_file_keys:
                image_service.storage.cleanup(file_key)
            raise
        self.db.refresh(template)
        return template

    def update_note(self, note_id: uuid.UUID, payload: NoteUpdateRequest) -> Note | None:
        # Die Zeilensperre macht Prüfung und Revisionsfortschritt atomar. Zwei
        # gleichzeitige PATCHes können dadurch nicht beide dieselbe Revision
        # erfolgreich überschreiben.
        note = self._get(note_id, for_update=True)
        if note is None:
            return None
        current_revision = int(note.revision or 1)
        if payload.base_revision is not None and payload.base_revision != current_revision:
            raise ConflictError(
                "Die Notiz wurde inzwischen an anderer Stelle geändert.",
                details={"current_revision": current_revision},
            )
        if payload.title is not None:
            note.title = payload.title
        if payload.body_json is not None:
            note.body_json = payload.body_json
            note.body_text = derive_body_text(payload.body_json)
            if not note.is_template:
                self._sync_links(note)
                self._sync_tasks(note)
        if payload.title is not None or payload.body_json is not None:
            note.revision = current_revision + 1
            if not note.is_template:
                self._record_revision(note, reason=payload.history_reason)
        # Notizbuch-Wechsel ist Metadaten (wie Tags/Papierkorb): kein Fortschritt
        # der Inhaltsrevision, kein Wiederherstellungspunkt. Nur wirksam, wenn das
        # Feld tatsächlich gesendet wurde (``None`` = aus Notizbuch nehmen).
        if "notebook_id" in payload.model_fields_set:
            note.notebook_id = self._resolve_notebook_id(payload.notebook_id)
        # Anheften ist ebenfalls Metadaten (kein Revisions-Bump).
        if "is_favorite" in payload.model_fields_set and payload.is_favorite is not None:
            note.is_favorite = bool(payload.is_favorite)
        self.db.commit()
        self.db.refresh(note)
        return note

    # --- Versionsverlauf ----------------------------------------------------
    def list_revisions(self, note_id: uuid.UUID, *, limit: int = 50) -> NoteRevisionListResponse:
        note = self._get(note_id, include_deleted=True)
        if note is None:
            raise NotFoundError("Notiz nicht gefunden", details={"note_id": str(note_id)})
        bounded_limit = max(1, min(int(limit), _NOTE_HISTORY_LIMIT))
        rows = self.db.scalars(
            select(NoteRevision)
            .where(NoteRevision.note_id == note_id, NoteRevision.owner_id == self.owner_id)
            .order_by(NoteRevision.updated_at.desc(), NoteRevision.created_at.desc())
            .limit(bounded_limit)
        ).all()
        total = int(
            self.db.scalar(
                select(func.count())
                .select_from(NoteRevision)
                .where(NoteRevision.note_id == note_id, NoteRevision.owner_id == self.owner_id)
            )
            or 0
        )
        return NoteRevisionListResponse(
            items=[
                NoteRevisionListItem(
                    id=row.id,
                    note_id=row.note_id,
                    note_revision=row.note_revision,
                    reason=row.reason,
                    title=row.title,
                    preview=_search_preview(row.body_text or "", None),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            total=total,
        )

    def get_revision(self, note_id: uuid.UUID, revision_id: uuid.UUID) -> NoteRevision:
        revision = self.db.scalar(
            select(NoteRevision).where(
                NoteRevision.id == revision_id,
                NoteRevision.note_id == note_id,
                NoteRevision.owner_id == self.owner_id,
            )
        )
        if revision is None:
            raise NotFoundError("Version nicht gefunden", details={"revision_id": str(revision_id)})
        return revision

    def checkpoint_revision(self, note_id: uuid.UUID, reason: NoteHistoryReason) -> NoteRevision:
        note = self._get(note_id, for_update=True)
        if note is None:
            raise NotFoundError("Notiz nicht gefunden", details={"note_id": str(note_id)})
        revision = self._checkpoint_revision(note, reason)
        self.db.commit()
        self.db.refresh(revision)
        return revision

    def restore_revision(
        self,
        note_id: uuid.UUID,
        revision_id: uuid.UUID,
        *,
        base_revision: int,
    ) -> Note:
        note = self._get(note_id, for_update=True)
        if note is None:
            raise NotFoundError("Notiz nicht gefunden", details={"note_id": str(note_id)})
        current_revision = int(note.revision or 1)
        if base_revision != current_revision:
            raise ConflictError(
                "Die Notiz wurde inzwischen an anderer Stelle geändert.",
                details={"current_revision": current_revision},
            )
        selected = self.get_revision(note_id, revision_id)
        if self._revision_matches_note(selected, note):
            self.db.commit()
            self.db.refresh(note)
            return note

        self._checkpoint_revision(note, "before_restore")
        note.title = selected.title or ""
        note.body_json = copy.deepcopy(selected.body_json) or EMPTY_DOC
        note.body_text = derive_body_text(note.body_json)
        note.revision = current_revision + 1
        if not note.is_template:
            self._sync_links(note)
            self._sync_tasks(note)
            self._record_revision(note, reason="restore", force_new=True)
        self.db.commit()
        self.db.refresh(note)
        return note

    # --- Tags (gemeinsames Vokabular mit Dokumenten) -------------------------
    def _get_or_create_tag(self, name: str) -> Tag | None:
        """Owner-scoped, case-insensitive: vorhandenes Tag finden oder anlegen."""
        normalized = " ".join(str(name or "").split()).strip()
        if not normalized:
            return None

        def _lookup() -> Tag | None:
            stmt = select(Tag).where(
                func.lower(Tag.name) == normalized.lower(), Tag.owner_id == self.owner_id
            )
            return self.db.execute(stmt).scalar_one_or_none()

        existing = _lookup()
        if existing is not None:
            return existing
        try:
            with self.db.begin_nested():
                self.db.add(Tag(owner_id=self.owner_id, name=normalized))
                self.db.flush()
        except IntegrityError:
            pass
        return _lookup()

    def set_tags(
        self,
        note_id: uuid.UUID,
        *,
        tag_ids: list[uuid.UUID] | None = None,
        names: list[str] | None = None,
    ) -> Note | None:
        """Setzt die Tags einer Notiz.

        ``tag_ids`` verknüpft bestehende (owner-eigene) Tags, ``names`` legt
        unbekannte an. Beide werden vereinigt und dedupliziert.
        """
        note = self._get(note_id)
        if note is None:
            return None
        resolved: list[Tag] = []
        seen: set[uuid.UUID] = set()

        if tag_ids:
            owned = self.db.scalars(
                select(Tag).where(Tag.owner_id == self.owner_id, Tag.id.in_(list(tag_ids)))
            ).all()
            by_id = {t.id: t for t in owned}
            for tid in tag_ids:  # Eingabereihenfolge erhalten
                tag = by_id.get(tid)
                if tag is not None and tag.id not in seen:
                    seen.add(tag.id)
                    resolved.append(tag)

        for name in names or []:
            tag = self._get_or_create_tag(name)
            if tag is not None and tag.id not in seen:
                seen.add(tag.id)
                resolved.append(tag)

        note.tags = resolved
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
                Note.is_template.is_(False),
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
                tags=_tag_refs(n),
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
        file_keys = [
            key
            for key in self.db.scalars(
                select(NoteImage.file_key).where(
                    NoteImage.note_id == note.id,
                    NoteImage.owner_id == self.owner_id,
                )
            ).all()
            if isinstance(key, str) and key
        ]
        self.db.delete(note)
        self.db.commit()
        if file_keys:
            storage = NoteImageStorage()
            for file_key in file_keys:
                storage.cleanup(file_key)
        return True

    def bulk_action(self, action: str, ids: list[uuid.UUID]) -> int:
        """Sammelaktion des Verwaltungsrasters. Gibt die Zahl betroffener
        Notizen zurück; ungültige/fremde IDs werden still übersprungen."""
        affected = 0
        for note_id in ids:
            if action == "trash":
                done = self.trash_note(note_id) is not None
            elif action == "restore":
                done = self.restore_note(note_id) is not None
            elif action == "delete":
                done = self.delete_note(note_id)
            elif action == "template":
                done = self.save_as_template(note_id) is not None
            else:
                done = False
            if done:
                affected += 1
        return affected

    def empty_trash(self) -> int:
        notes = list(
            self.db.scalars(
                select(Note).where(Note.owner_id == self.owner_id, Note.is_deleted.is_(True))
            ).all()
        )
        note_ids = [note.id for note in notes]
        file_keys = [
            key
            for key in (
                self.db.scalars(
                    select(NoteImage.file_key).where(
                        NoteImage.note_id.in_(note_ids),
                        NoteImage.owner_id == self.owner_id,
                    )
                ).all()
                if note_ids
                else []
            )
            if isinstance(key, str) and key
        ]
        for note in notes:
            self.db.delete(note)
        if notes:
            self.db.commit()
        if file_keys:
            storage = NoteImageStorage()
            for file_key in file_keys:
                storage.cleanup(file_key)
        return len(notes)
