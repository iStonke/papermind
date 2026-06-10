"""Backfill kanonischer Korrespondenten für bestehende Dokumente."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.correspondent_matching import CorrespondentMatchingService


@dataclass(frozen=True)
class CorrespondentBackfillHit:
    document_id: str
    title: str
    original_filename: str
    sender: str | None
    correspondent_id: str
    correspondent_name: str
    matched_by: str
    matched_value: str
    score: int


@dataclass(frozen=True)
class CorrespondentBackfillResult:
    scanned: int
    matched: int
    updated: int
    skipped_low_score: int
    dry_run: bool
    min_score: int
    hits: list[CorrespondentBackfillHit]

    def to_dict(self) -> dict[str, object]:
        return {
            "scanned": self.scanned,
            "matched": self.matched,
            "updated": self.updated,
            "skipped_low_score": self.skipped_low_score,
            "dry_run": self.dry_run,
            "min_score": self.min_score,
            "hits": [asdict(hit) for hit in self.hits],
        }


@dataclass(frozen=True)
class UnresolvedCorrespondentItem:
    document_id: str
    title: str
    original_filename: str
    sender: str | None
    document_type: str | None
    document_date: str | None
    ai_status: str
    ocr_status: str
    text_available: bool
    text_excerpt: str | None


@dataclass(frozen=True)
class UnresolvedCorrespondentReport:
    scanned: int
    unresolved: int
    include_deleted: bool
    items: list[UnresolvedCorrespondentItem]

    def to_dict(self) -> dict[str, object]:
        return {
            "scanned": self.scanned,
            "unresolved": self.unresolved,
            "include_deleted": self.include_deleted,
            "items": [asdict(item) for item in self.items],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Ungeklärte Korrespondenten",
            "",
            f"- Gescannt: {self.scanned}",
            f"- Offen: {self.unresolved}",
            f"- Papierkorb einbezogen: {'ja' if self.include_deleted else 'nein'}",
            "",
        ]
        for index, item in enumerate(self.items, start=1):
            lines.extend(
                [
                    f"## {index}. {item.title or item.original_filename}",
                    "",
                    f"- Dokument-ID: `{item.document_id}`",
                    f"- Dateiname: `{item.original_filename}`",
                    f"- Erkannter Absender: {item.sender or '_leer_'}",
                    f"- Dokumenttyp: {item.document_type or '_leer_'}",
                    f"- Dokumentdatum: {item.document_date or '_leer_'}",
                    f"- AI/OCR-Status: `{item.ai_status}` / `{item.ocr_status}`",
                    "",
                    "```text",
                    item.text_excerpt or "",
                    "```",
                    "",
                    "Entscheidung: bestehender Korrespondent / neuer Korrespondent / Alias / leer lassen",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


class CorrespondentBackfillService:
    """Ordnet Dokumente ohne ``correspondent_id`` bestehenden Korrespondenten zu."""

    def __init__(self, db: Session, owner_id=None):
        self.db = db
        self.owner_id = owner_id
        self.matcher = CorrespondentMatchingService(db, owner_id)

    def run(
        self,
        *,
        limit: int = 200,
        dry_run: bool = True,
        min_score: int = 500,
        include_deleted: bool = False,
        text_chars: int = 6000,
    ) -> CorrespondentBackfillResult:
        stmt = (
            select(Document)
            .where(Document.correspondent_id.is_(None))
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        if not include_deleted:
            stmt = stmt.where(Document.is_deleted.is_(False))

        documents = self.db.execute(stmt).scalars().all()
        hits: list[CorrespondentBackfillHit] = []
        matched = 0
        updated = 0
        skipped_low_score = 0

        for document in documents:
            ocr_text = self._text_for_matching(document, max_chars=text_chars)
            match = self.matcher.resolve(
                sender=document.ai_sender,
                filename=document.original_filename,
                ocr_text=ocr_text,
            )
            if match is None:
                continue

            matched += 1
            if match.score < min_score:
                skipped_low_score += 1
                continue

            hits.append(
                CorrespondentBackfillHit(
                    document_id=str(document.id),
                    title=(document.display_name or document.original_filename or "").strip(),
                    original_filename=document.original_filename,
                    sender=document.ai_sender,
                    correspondent_id=str(match.correspondent_id),
                    correspondent_name=match.name,
                    matched_by=match.matched_by,
                    matched_value=match.matched_value,
                    score=match.score,
                )
            )
            if not dry_run:
                document.correspondent_id = uuid.UUID(str(match.correspondent_id))
                document.updated_at = func.now()
                updated += 1

        if not dry_run and updated:
            self.db.commit()

        return CorrespondentBackfillResult(
            scanned=len(documents),
            matched=matched,
            updated=updated,
            skipped_low_score=skipped_low_score,
            dry_run=dry_run,
            min_score=min_score,
            hits=hits,
        )

    def unresolved_report(
        self,
        *,
        limit: int = 200,
        include_deleted: bool = False,
        excerpt_chars: int = 700,
    ) -> UnresolvedCorrespondentReport:
        stmt = (
            select(Document)
            .where(
                Document.correspondent_id.is_(None),
                Document.flags["correspondent_review"].astext.is_distinct_from("ignored"),
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        if not include_deleted:
            stmt = stmt.where(Document.is_deleted.is_(False))

        documents = self.db.execute(stmt).scalars().all()
        items: list[UnresolvedCorrespondentItem] = []
        for document in documents:
            text = self._text_for_matching(document, max_chars=excerpt_chars)
            items.append(
                UnresolvedCorrespondentItem(
                    document_id=str(document.id),
                    title=(document.display_name or document.original_filename or "").strip(),
                    original_filename=document.original_filename,
                    sender=document.ai_sender,
                    document_type=document.document_type,
                    document_date=document.document_date.isoformat() if document.document_date else None,
                    ai_status=document.ai_status,
                    ocr_status=document.ocr_status,
                    text_available=bool(text.strip()),
                    text_excerpt=self._compact_excerpt(text, max_chars=excerpt_chars),
                )
            )

        return UnresolvedCorrespondentReport(
            scanned=len(documents),
            unresolved=len(items),
            include_deleted=include_deleted,
            items=items,
        )

    def _text_for_matching(self, document: Document, *, max_chars: int) -> str:
        text = str(document.text_content or "").strip()
        if text:
            return text[:max_chars]

        rows = (
            self.db.execute(
                select(DocumentChunk.text)
                .where(DocumentChunk.doc_id == document.id)
                .order_by(DocumentChunk.chunk_index.asc())
                .limit(8)
            )
            .scalars()
            .all()
        )
        return " ".join(str(row or "").strip() for row in rows if str(row or "").strip())[:max_chars]

    @staticmethod
    def _compact_excerpt(value: str, *, max_chars: int) -> str | None:
        excerpt = " ".join(str(value or "").split())
        if not excerpt:
            return None
        if len(excerpt) <= max_chars:
            return excerpt
        return excerpt[: max(0, max_chars - 1)].rstrip() + "…"
