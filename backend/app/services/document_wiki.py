"""Small, source-linked LLM-Wiki cache for document chat.

PaperMind already obtains a concise, structured classification during import.
This service compiles that result and trustworthy document metadata into a
persistent Markdown page. Reusing the import result is important on the Pi:
building the wiki must not add a second expensive generation per document.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_wiki_entry import DocumentWikiEntry
from app.services.wiki import WikiService

_SUMMARY_LIMIT = 700
_MAX_ENTRIES = 4


def _compact(value: object | None, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).strip()
    if limit is not None and len(text) > limit:
        return f"{text[:limit].rstrip()}…"
    return text


def _display_title(document: Document) -> str:
    return _compact(document.display_name or document.original_filename or "Dokument") or "Dokument"


def _format_amount(amount: Decimal | None, currency: str | None) -> str:
    if amount is None:
        return ""
    rendered = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{rendered} {_compact(currency) or 'EUR'}"


def render_document_wiki_entry(document: Document) -> str:
    """Create a compact Markdown page with explicit source/provenance wording."""
    lines = [
        f"# {_display_title(document)}",
        "",
        "> Automatisch verdichtete Arbeitsnotiz. Bei Konflikten gilt immer das Originaldokument.",
        "",
        "## Fakten aus Dokument-Metadaten",
    ]
    facts = (
        ("Dokumenttyp", document.document_type or document.ai_document_type),
        ("Datum", document.document_date or document.ai_document_date),
        ("Absender", document.ai_sender),
        ("Empfänger", document.ai_recipient),
        ("Betrag", _format_amount(document.ai_amount, document.ai_currency)),
    )
    for label, value in facts:
        compact = _compact(value)
        if compact:
            lines.append(f"- {label}: {compact}")

    summary = _compact(document.ai_summary, _SUMMARY_LIMIT)
    if summary:
        lines.extend(["", "## KI-Zusammenfassung", summary])
    else:
        lines.extend(["", "## Status", "- Noch keine KI-Zusammenfassung verfügbar."])

    lines.extend(["", "## Herkunft", "- Quelle: dieses Originaldokument; Seitenbelege werden aus den Originalauszügen geliefert."])
    return "\n".join(lines)


class DocumentWikiService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def refresh_document(self, document: Document) -> DocumentWikiEntry:
        """Refresh legacy note and the trustworthy versioned wiki.

        ``document_wiki_entries`` remains a compatibility cache while the new
        wiki stores source-grounded atomic claims. Legacy prose is never used as
        factual evidence by the chat.
        """
        content = render_document_wiki_entry(document)
        entry = self.db.get(DocumentWikiEntry, document.id)
        if entry is None:
            entry = DocumentWikiEntry(
                document_id=document.id,
                source_text_hash=document.text_hash,
                content=content,
            )
            self.db.add(entry)
        elif entry.source_text_hash != document.text_hash or entry.content != content:
            entry.source_text_hash = document.text_hash
            entry.content = content
            entry.updated_at = datetime.now(timezone.utc)
        owner_id = self.owner_id or document.owner_id
        WikiService(self.db, owner_id).refresh_document(document.id, commit=False)
        return entry

    def render_for_documents(
        self,
        document_ids: Iterable[uuid.UUID],
        *,
        limit: int = _MAX_ENTRIES,
        max_chars: int = 2200,
    ) -> str:
        unique_ids = list(dict.fromkeys(document_ids))[: max(0, limit)]
        if not unique_ids:
            return ""
        stmt = select(DocumentWikiEntry.document_id, DocumentWikiEntry.content).where(
            DocumentWikiEntry.document_id.in_(unique_ids)
        )
        if self.owner_id is not None:
            stmt = stmt.join(Document, Document.id == DocumentWikiEntry.document_id).where(Document.owner_id == self.owner_id)
        rows = self.db.execute(stmt).all()
        by_id = {doc_id: content for doc_id, content in rows}
        pages = [by_id[doc_id] for doc_id in unique_ids if doc_id in by_id]
        if not pages:
            return ""
        rendered = "\n\n---\n\n".join(pages)
        return _compact(rendered, max(1, max_chars))
