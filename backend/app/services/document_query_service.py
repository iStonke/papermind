"""Read-only document queries, including filtering, ranking and summary mapping."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session, load_only, noload, selectinload

from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.document_retention import DocumentRetention
from app.models.document_tag import document_tags
from app.models.tag import Tag
from app.schemas.documents import (
    CalendarDayCount,
    CalendarMonthCount,
    DocumentAttentionFilter,
    DocumentCalendarResponse,
    DocumentListResponse,
    DocumentSearchScope,
    DocumentSortField,
    DocumentStatus,
    DocumentStatusListResponse,
    DocumentStatusRead,
    DocumentSummary,
    SortOrder,
)
from app.services.document_search import (
    build_scoped_search_filter,
    build_ts_query_expr,
    normalize_search_query,
)
from app.services.settings import SettingsService


settings = get_settings()
FTS_HEADLINE_OPTIONS = (
    "StartSel=<mark>,StopSel=</mark>,MaxFragments=2,MinWords=6,"
    "MaxWords=16,ShortWord=2,FragmentDelimiter= … "
)


class DocumentQueryService:
    """Encapsulates the complete read path for the document overview."""

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None) -> None:
        self.db = db
        self.owner_id = owner_id

    def _scope(self, stmt):
        return stmt.where(Document.owner_id == self.owner_id) if self.owner_id is not None else stmt

    @staticmethod
    def summary_load_options():
        return (
            load_only(
                Document.id,
                Document.original_filename,
                Document.display_name,
                Document.duplicate_of_doc_id,
                Document.duplicate_kind,
                Document.duplicate_score,
                Document.is_unread,
                Document.is_deleted,
                Document.is_favorite,
                Document.document_date,
                Document.document_date_source,
                Document.document_date_confidence,
                Document.document_date_candidates,
                Document.document_type,
                Document.correspondent_id,
                Document.status,
                Document.ocr_status,
                Document.ocr_quality_status,
                Document.ocr_confidence_score,
                Document.embedding_status,
                Document.ai_document_type,
                Document.ai_status,
                Document.created_at,
                Document.updated_at,
            ),
            selectinload(Document.tags),
            noload(Document.files),
            noload(Document.jobs),
            noload(Document.chunks),
        )

    def statuses(self, document_ids: list[uuid.UUID]) -> DocumentStatusListResponse:
        unique_ids = list(dict.fromkeys(document_ids))
        if not unique_ids:
            return DocumentStatusListResponse(items=[])
        rows = self.db.execute(
            self._scope(
                select(
                    Document.id,
                    Document.status,
                    Document.ocr_status,
                    Document.ocr_quality_status,
                    Document.ocr_confidence_score,
                    Document.updated_at,
                ).where(Document.id.in_(unique_ids))
            )
        ).all()
        return DocumentStatusListResponse(
            items=[
                DocumentStatusRead(
                    id=row.id,
                    status=row.status,
                    ocr_status=row.ocr_status,
                    ocr_quality_status=row.ocr_quality_status,
                    ocr_confidence_score=row.ocr_confidence_score,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]
        )

    def _apply_filters(
        self,
        stmt,
        tag: str | None,
        tag_ids: list[uuid.UUID] | None,
        untagged: bool,
        status: DocumentStatus | None,
        date_from: date | None,
        date_to: date | None,
        recent_imports: bool,
        *,
        in_trash: bool,
        favorites_only: bool,
        without_text: bool,
        document_type: str | None,
        correspondent_id: uuid.UUID | None,
        attention: DocumentAttentionFilter | None,
    ):
        stmt = stmt.where(Document.is_deleted.is_(True if in_trash else False))
        if favorites_only:
            stmt = stmt.where(Document.is_favorite.is_(True))
        if without_text:
            stmt = stmt.where(Document.text_source == "none")

        normalized_tag_ids = list(dict.fromkeys(tag_ids or []))
        if untagged:
            tag_relation = select(document_tags.c.document_id).where(
                document_tags.c.document_id == Document.id
            )
            stmt = stmt.where(~tag_relation.exists())
        elif normalized_tag_ids:
            matching_documents = (
                select(document_tags.c.document_id)
                .where(document_tags.c.tag_id.in_(normalized_tag_ids))
                .group_by(document_tags.c.document_id)
                .having(func.count(func.distinct(document_tags.c.tag_id)) == len(normalized_tag_ids))
            )
            stmt = stmt.where(Document.id.in_(matching_documents))
        elif tag:
            tag_value = tag.strip()
            if not tag_value:
                return stmt.where(False)
            try:
                tag_id = uuid.UUID(tag_value)
                matching_documents = select(document_tags.c.document_id).where(
                    document_tags.c.tag_id == tag_id
                )
            except ValueError:
                matching_documents = (
                    select(document_tags.c.document_id)
                    .join(Tag, Tag.id == document_tags.c.tag_id)
                    .where(func.lower(Tag.name) == tag_value.lower())
                )
            stmt = stmt.where(Document.id.in_(matching_documents))

        if status:
            stmt = stmt.where(Document.status == status.value)
        if document_type:
            normalized_type = " ".join(str(document_type).split()).strip()
            if not normalized_type:
                return stmt.where(False)
            stmt = stmt.where(func.lower(Document.document_type) == normalized_type.lower())
        if correspondent_id is not None:
            stmt = stmt.where(Document.correspondent_id == correspondent_id)
        if recent_imports:
            runtime_settings = SettingsService(self.db).get_settings()
            threshold = datetime.now(timezone.utc) - timedelta(
                hours=max(1, int(runtime_settings.documents.recent_import_window_hours))
            )
            stmt = stmt.where(Document.created_at >= threshold)
        if date_from:
            stmt = stmt.where(Document.document_date >= date_from)
        if date_to:
            stmt = stmt.where(Document.document_date <= date_to)
        return self._apply_attention_filter(stmt, attention) if attention else stmt

    @staticmethod
    def _apply_attention_filter(stmt, attention: DocumentAttentionFilter):
        if attention == DocumentAttentionFilter.unread:
            return stmt.where(Document.is_unread.is_(True))
        if attention == DocumentAttentionFilter.unclassified:
            return stmt.where(Document.ai_status.in_(("pending", "error")))
        if attention == DocumentAttentionFilter.without_document_type:
            return stmt.where(func.coalesce(func.trim(Document.document_type), "") == "")
        if attention == DocumentAttentionFilter.ocr_issues:
            return stmt.where(
                or_(
                    Document.text_source == "none",
                    Document.ocr_quality_status.in_(("warning", "error")),
                )
            )
        if attention == DocumentAttentionFilter.retention_due:
            today = datetime.now(timezone.utc).date()
            due_ids = select(DocumentRetention.document_id).where(
                DocumentRetention.retain_until.is_not(None),
                DocumentRetention.retain_until >= today,
                DocumentRetention.retain_until <= today + timedelta(days=30),
            )
            return stmt.where(Document.id.in_(due_ids))
        return stmt

    @staticmethod
    def _as_summary(document: Document) -> DocumentSummary:
        summary = DocumentSummary.model_validate(document, from_attributes=True)
        summary.is_duplicate = document.duplicate_of_doc_id is not None
        return summary

    def _attach_summary_correspondents(self, items: list[DocumentSummary]) -> None:
        correspondent_ids = {item.correspondent_id for item in items if item.correspondent_id is not None}
        if not correspondent_ids:
            return
        stmt = select(Correspondent.id, Correspondent.name).where(Correspondent.id.in_(correspondent_ids))
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        names = dict(self.db.execute(stmt).all())
        for item in items:
            if item.correspondent_id is not None:
                item.correspondent_name = names.get(item.correspondent_id)

    def calendar_counts(
        self,
        *,
        year: int,
        month: int,
        q: str | None = None,
        tag: str | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        untagged: bool = False,
        status: DocumentStatus | None = None,
        in_trash: bool = False,
        favorites_only: bool = False,
        without_text: bool = False,
        document_type: str | None = None,
        correspondent_id: uuid.UUID | None = None,
        search_scope: DocumentSearchScope = DocumentSearchScope.all,
        attention: DocumentAttentionFilter | None = None,
    ) -> DocumentCalendarResponse:
        """Zählt Dokumente nach Dokumentdatum für die Kalenderansicht.

        Wendet dieselben Filter/Suche wie ``list_documents`` an – nur den
        Zeitraum steuert der Kalender selbst (kein date_from/date_to von außen).
        """
        base = self._apply_filters(
            self._scope(select(Document.id, Document.document_date)),
            tag, tag_ids, untagged, status, None, None, recent_imports=False,
            in_trash=in_trash, favorites_only=favorites_only, without_text=without_text,
            document_type=document_type, correspondent_id=correspondent_id, attention=attention,
        )
        normalized_query = normalize_search_query(q, max_length=settings.search_query_max_length)
        if normalized_query:
            if search_scope == DocumentSearchScope.all:
                ts_query_expr = build_ts_query_expr(normalized_query, settings.fts_regconfig)
                base = base.where(Document.search_vector.op("@@")(ts_query_expr))
            else:
                scoped_filter = build_scoped_search_filter(normalized_query, search_scope)
                if scoped_filter is not None:
                    base = base.where(scoped_filter)

        sub = base.where(Document.document_date.is_not(None)).subquery()
        doc_date = sub.c.document_date
        year_expr = func.extract("year", doc_date)
        month_expr = func.extract("month", doc_date)
        day_expr = func.extract("day", doc_date)

        available_years = [
            int(row[0])
            for row in self.db.execute(
                select(year_expr).select_from(sub).distinct().order_by(year_expr)
            ).all()
        ]

        month_map = {
            int(m): int(c)
            for m, c in self.db.execute(
                select(month_expr, func.count()).select_from(sub)
                .where(year_expr == year).group_by(month_expr)
            ).all()
        }
        months = [CalendarMonthCount(month=m, count=month_map.get(m, 0)) for m in range(1, 13)]

        days = [
            CalendarDayCount(day=int(d), count=int(c))
            for d, c in self.db.execute(
                select(day_expr, func.count()).select_from(sub)
                .where(year_expr == year, month_expr == month).group_by(day_expr).order_by(day_expr)
            ).all()
        ]
        month_total = sum(d.count for d in days)

        return DocumentCalendarResponse(
            year=year, month=month, days=days, months=months,
            available_years=available_years, month_total=month_total,
        )

    def list_documents(
        self,
        q: str | None,
        tag: str | None,
        tag_ids: list[uuid.UUID] | None,
        untagged: bool,
        status: DocumentStatus | None,
        date_from: date | None,
        date_to: date | None,
        recent_imports: bool,
        sort: DocumentSortField,
        order: SortOrder,
        limit: int,
        offset: int,
        include_total: bool = True,
        in_trash: bool = False,
        favorites_only: bool = False,
        without_text: bool = False,
        document_type: str | None = None,
        search_scope: DocumentSearchScope = DocumentSearchScope.all,
        attention: DocumentAttentionFilter | None = None,
        correspondent_id: uuid.UUID | None = None,
    ) -> DocumentListResponse:
        if date_from and date_to and date_from > date_to:
            raise BadRequestError(
                "date_from must be earlier than or equal to date_to",
                details={"date_from": str(date_from), "date_to": str(date_to)},
            )

        normalized_query = normalize_search_query(q, max_length=settings.search_query_max_length)
        filtered_stmt = self._apply_filters(
            self._scope(select(Document)), tag, tag_ids, untagged, status, date_from, date_to, recent_imports,
            in_trash=in_trash, favorites_only=favorites_only, without_text=without_text,
            document_type=document_type, correspondent_id=correspondent_id, attention=attention,
        )
        ts_query_expr = None
        if normalized_query:
            if search_scope == DocumentSearchScope.all:
                ts_query_expr = build_ts_query_expr(normalized_query, settings.fts_regconfig)
                filtered_stmt = filtered_stmt.where(Document.search_vector.op("@@")(ts_query_expr))
            else:
                scoped_filter = build_scoped_search_filter(normalized_query, search_scope)
                if scoped_filter is not None:
                    filtered_stmt = filtered_stmt.where(scoped_filter)

        direction = asc if order == SortOrder.asc else desc
        if sort in (DocumentSortField.document_date, DocumentSortField.doc_date):
            order_expr, secondary_order_expr = direction(Document.document_date).nullslast(), desc(Document.created_at)
        elif sort == DocumentSortField.updated_at:
            order_expr, secondary_order_expr = direction(Document.updated_at), desc(Document.id)
        elif sort == DocumentSortField.name:
            order_expr = direction(func.lower(func.coalesce(Document.display_name, Document.original_filename)))
            secondary_order_expr = desc(Document.created_at)
        elif sort in (DocumentSortField.is_unread, DocumentSortField.unread):
            order_expr, secondary_order_expr = direction(case((Document.is_unread.is_(True), 1), else_=0)), desc(Document.updated_at)
        elif sort in (DocumentSortField.is_favorite, DocumentSortField.favorite):
            order_expr, secondary_order_expr = direction(case((Document.is_favorite.is_(True), 1), else_=0)), desc(Document.updated_at)
        else:
            order_expr, secondary_order_expr = direction(Document.created_at), desc(Document.id)

        total = None
        if include_total:
            total_source = filtered_stmt.with_only_columns(Document.id).order_by(None).subquery()
            total = self.db.scalar(select(func.count()).select_from(total_source)) or 0

        if ts_query_expr is not None:
            rank_expr = func.ts_rank(Document.search_vector, ts_query_expr).label("search_rank")
            snippet_expr = func.ts_headline(
                settings.fts_regconfig,
                func.concat_ws(" ", func.coalesce(Document.display_name, ""), Document.original_filename,
                               func.coalesce(Document.notes, ""), func.coalesce(Document.text_content, "")),
                ts_query_expr,
                FTS_HEADLINE_OPTIONS,
            ).label("search_snippet")
            search_order = (order_expr, secondary_order_expr, desc(rank_expr)) if sort in (
                DocumentSortField.is_favorite, DocumentSortField.favorite
            ) else (desc(rank_expr), order_expr, secondary_order_expr)
            rows = self.db.execute(
                filtered_stmt.add_columns(rank_expr, snippet_expr)
                .options(*self.summary_load_options())
                .order_by(*search_order).limit(limit).offset(offset)
            ).all()
            items = []
            for document, rank, snippet in rows:
                summary = self._as_summary(document)
                summary.rank = float(rank) if rank is not None else None
                summary.snippet = (snippet or "").strip() or None
                items.append(summary)
        else:
            rows = self.db.execute(
                filtered_stmt.options(*self.summary_load_options())
                .order_by(order_expr, secondary_order_expr).limit(limit).offset(offset)
            ).scalars().unique().all()
            items = [self._as_summary(document) for document in rows]

        self._attach_summary_correspondents(items)
        return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)
