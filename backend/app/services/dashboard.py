import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select, true
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.document_retention import DocumentRetention
from app.models.document_tag import document_tags
from app.models.document_type import DocumentType
from app.models.tag import Tag
from app.models.search_event import SearchEvent
from app.schemas.dashboard import (
    DashboardAttention,
    DashboardCorrespondent,
    DashboardMonthPoint,
    DashboardOverviewResponse,
    DashboardRecentItem,
    DashboardSearchTerm,
    DashboardStats,
    DashboardStoragePoint,
    DashboardTagShare,
    DashboardTypeShare,
    DashboardYearPoint,
)

logger = logging.getLogger("papermind.dashboard")

# Fenster, in dem eine Aufbewahrungsfrist als "läuft bald ab" gilt.
RETENTION_DUE_WINDOW_DAYS = 30
# Wie viele Monate die "Dokumente pro Monat"-Reihe zurückreicht.
MONTHS_BACK = 12
# Obergrenze für die Jahresreihe: schützt vor absurden Datumsausreißern
# (z.B. Fehl-OCR mit Jahr 1900), die die Achse sonst unbrauchbar dehnen.
MAX_HISTORY_YEARS = 30


def _first_of_month(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    """Verschiebt ein Datum um `months` Monate (auch negativ), Tag auf 1 fixiert."""
    total = (value.year * 12 + (value.month - 1)) + months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


class DashboardService:
    """Read-only Aggregationen über den Dokumentbestand eines Owners."""

    def __init__(self, db: Session, owner_id=None):
        self.db = db
        self.owner_id = owner_id

    def _owner_cond(self):
        return (Document.owner_id == self.owner_id) if self.owner_id is not None else true()

    def _active_doc(self):
        return and_(Document.is_deleted.is_(False), self._owner_cond())

    def get_overview(self) -> DashboardOverviewResponse:
        today = datetime.now(timezone.utc).date()
        active = self._active_doc()

        stats = self._stats(today, active)
        per_month, per_month_total = self._documents_per_month(today, active)
        per_year = self._documents_per_year(today, active)
        top_correspondents = self._top_correspondents(active)
        tag_distribution, tag_count_total = self._tag_distribution(active)
        type_distribution, type_count_total = self._type_distribution(active)
        storage_series = self._storage_series(today, active)
        top_searches = self._top_searches()
        attention = self._attention(today, active)
        recent = self._recent(active)

        return DashboardOverviewResponse(
            stats=stats,
            documents_per_month=per_month,
            documents_per_month_total=per_month_total,
            documents_per_year=per_year,
            top_correspondents=top_correspondents,
            tag_distribution=tag_distribution,
            tag_count_total=tag_count_total,
            type_distribution=type_distribution,
            type_count_total=type_count_total,
            storage_series=storage_series,
            top_searches=top_searches,
            attention=attention,
            recent=recent,
        )

    # ── Kennzahlen ──────────────────────────────────────────────────────────
    def _stats(self, today: date, active) -> DashboardStats:
        month_start = _first_of_month(today)
        prev_month_start = _add_months(month_start, -1)

        row = self.db.execute(
            select(
                func.count(Document.id).label("total"),
                func.coalesce(func.sum(Document.file_size_bytes), 0).label("storage"),
                func.coalesce(
                    func.sum(case((Document.created_at >= month_start, 1), else_=0)), 0
                ).label("this_month"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    Document.created_at >= prev_month_start,
                                    Document.created_at < month_start,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("prev_month"),
            ).where(active)
        ).one()

        total = int(row.total or 0)
        storage_bytes = int(row.storage or 0)
        this_month = int(row.this_month or 0)
        prev_month = int(row.prev_month or 0)

        total_trend_pct: float | None = None
        if prev_month > 0:
            total_trend_pct = round((this_month - prev_month) / prev_month * 100.0, 1)

        # Korrespondenten des Owners (gesamt + neu in diesem Monat).
        corr_owner = (Correspondent.owner_id == self.owner_id) if self.owner_id is not None else true()
        corr_total = int(self.db.scalar(select(func.count(Correspondent.id)).where(corr_owner)) or 0)
        corr_new = int(
            self.db.scalar(
                select(func.count(Correspondent.id)).where(
                    corr_owner, Correspondent.created_at >= month_start
                )
            )
            or 0
        )

        # Tags des Owners (gesamt).
        tag_owner = (Tag.owner_id == self.owner_id) if self.owner_id is not None else true()
        try:
            tags_total = int(self.db.scalar(select(func.count(Tag.id)).where(tag_owner)) or 0)
        except ProgrammingError:
            self.db.rollback()
            tags_total = 0

        type_owner = (DocumentType.owner_id == self.owner_id) if self.owner_id is not None else true()
        try:
            document_types_total = int(self.db.scalar(select(func.count(DocumentType.id)).where(type_owner)) or 0)
        except ProgrammingError:
            self.db.rollback()
            document_types_total = 0

        untagged = self._untagged_count(active)
        untagged_pct = round(untagged / total * 100.0, 1) if total > 0 else 0.0

        return DashboardStats(
            documents_total=total,
            this_month=this_month,
            correspondents=corr_total,
            tags=tags_total,
            document_types=document_types_total,
            storage_bytes=storage_bytes,
            storage_limit_bytes=None,
            total_trend_pct=total_trend_pct,
            correspondents_new=corr_new,
            untagged_pct=untagged_pct,
        )

    def _untagged_count(self, active) -> int:
        stmt = select(func.count(Document.id)).where(
            active,
            ~select(document_tags.c.document_id)
            .where(document_tags.c.document_id == Document.id)
            .exists(),
        )
        return int(self.db.scalar(stmt) or 0)

    # ── Dokumente pro Monat (nach Dokumentdatum) ────────────────────────────
    def _documents_per_month(self, today: date, active):
        month_start = _first_of_month(today)
        window_start = _add_months(month_start, -(MONTHS_BACK - 1))

        bucket = func.to_char(func.date_trunc("month", Document.document_date), "YYYY-MM")
        rows = self.db.execute(
            select(bucket.label("month"), func.count(Document.id).label("count"))
            .where(active, Document.document_date.is_not(None), Document.document_date >= window_start)
            .group_by(bucket)
        ).all()
        counts = {row.month: int(row.count or 0) for row in rows}

        series: list[DashboardMonthPoint] = []
        total = 0
        for offset in range(MONTHS_BACK):
            m = _add_months(window_start, offset)
            key = f"{m.year:04d}-{m.month:02d}"
            value = counts.get(key, 0)
            total += value
            series.append(DashboardMonthPoint(month=key, count=value))
        return series, total

    # ── Dokumente pro Jahr (volle Historie, nach Dokumentdatum) ─────────────
    def _documents_per_year(self, today: date, active) -> list[DashboardYearPoint]:
        year_expr = func.extract("year", Document.document_date)
        rows = self.db.execute(
            select(year_expr.label("year"), func.count(Document.id).label("count"))
            .where(active, Document.document_date.is_not(None))
            .group_by(year_expr)
        ).all()
        if not rows:
            return []

        counts = {int(row.year): int(row.count or 0) for row in rows}
        current_year = today.year
        # Startjahr: frühestes vorhandenes Jahr, aber gegen Ausreißer gedeckelt.
        earliest = min(counts)
        start_year = max(earliest, current_year - MAX_HISTORY_YEARS)
        # Dokumente vor dem Deckel in das Startjahr zusammenfassen, damit die
        # Gesamtsumme stimmt und kein Bestand "verschwindet".
        clipped = sum(count for year, count in counts.items() if year < start_year)

        series: list[DashboardYearPoint] = []
        for year in range(start_year, current_year + 1):
            value = counts.get(year, 0)
            if year == start_year:
                value += clipped
            series.append(DashboardYearPoint(year=year, count=value))
        return series

    # ── Top-Korrespondenten ─────────────────────────────────────────────────
    def _top_correspondents(self, active, limit: int = 12) -> list[DashboardCorrespondent]:
        rows = self.db.execute(
            select(Correspondent.name, func.count(Document.id).label("count"))
            .join(Correspondent, Correspondent.id == Document.correspondent_id)
            .where(active)
            .group_by(Correspondent.name)
            .order_by(func.count(Document.id).desc(), Correspondent.name.asc())
            .limit(limit)
        ).all()
        return [DashboardCorrespondent(name=row.name, count=int(row.count or 0)) for row in rows]

    # ── Tag-Verteilung ──────────────────────────────────────────────────────
    def _tag_distribution(self, active, limit: int = 6):
        rows = self.db.execute(
            select(Tag.name, func.count(Document.id).label("count"))
            .select_from(document_tags)
            .join(Document, Document.id == document_tags.c.document_id)
            .join(Tag, Tag.id == document_tags.c.tag_id)
            .where(active)
            .group_by(Tag.name)
            .order_by(func.count(Document.id).desc(), Tag.name.asc())
            .limit(limit)
        ).all()
        distribution = [DashboardTagShare(tag=row.name, count=int(row.count or 0)) for row in rows]

        total = int(
            self.db.scalar(
                select(func.count(func.distinct(document_tags.c.tag_id)))
                .select_from(document_tags)
                .join(Document, Document.id == document_tags.c.document_id)
                .where(active)
            )
            or 0
        )
        return distribution, total

    # ── Dokumenttyp-Verteilung ──────────────────────────────────────────────
    def _type_distribution(self, active, limit: int = 6):
        rows = self.db.execute(
            select(Document.document_type, func.count(Document.id).label("count"))
            .where(active, Document.document_type.is_not(None), Document.document_type != "")
            .group_by(Document.document_type)
            .order_by(func.count(Document.id).desc(), Document.document_type.asc())
            .limit(limit)
        ).all()
        distribution = [DashboardTypeShare(type=row.document_type, count=int(row.count or 0)) for row in rows]

        total = int(
            self.db.scalar(
                select(func.count(func.distinct(Document.document_type))).where(
                    active, Document.document_type.is_not(None), Document.document_type != ""
                )
            )
            or 0
        )
        return distribution, total

    # ── Speicher-Wachstum (kumuliert je Monat, nach Ablagedatum) ────────────
    def _storage_series(self, today: date, active) -> list[DashboardStoragePoint]:
        month_start = _first_of_month(today)
        window_start = _add_months(month_start, -(MONTHS_BACK - 1))

        bucket = func.to_char(func.date_trunc("month", Document.created_at), "YYYY-MM")
        rows = self.db.execute(
            select(bucket.label("month"), func.coalesce(func.sum(Document.file_size_bytes), 0).label("bytes"))
            .where(active)
            .group_by(bucket)
        ).all()
        per_month = {row.month: int(row.bytes or 0) for row in rows}

        # Sockel: alles, was vor dem Fenster abgelegt wurde.
        baseline = sum(size for month, size in per_month.items() if month < f"{window_start.year:04d}-{window_start.month:02d}")

        series: list[DashboardStoragePoint] = []
        running = baseline
        for offset in range(MONTHS_BACK):
            m = _add_months(window_start, offset)
            key = f"{m.year:04d}-{m.month:02d}"
            running += per_month.get(key, 0)
            series.append(DashboardStoragePoint(month=key, bytes=running))
        return series

    # ── Top-Suchbegriffe ────────────────────────────────────────────────────
    def _top_searches(self, limit: int = 5) -> list[DashboardSearchTerm]:
        try:
            key = func.lower(SearchEvent.term)
            stmt = (
                select(func.min(SearchEvent.term).label("term"), func.count().label("count"))
                .group_by(key)
                .order_by(func.count().desc(), func.min(SearchEvent.term).asc())
                .limit(limit)
            )
            if self.owner_id is not None:
                stmt = stmt.where(SearchEvent.owner_id == self.owner_id)
            return [DashboardSearchTerm(term=row.term, count=int(row.count or 0)) for row in self.db.execute(stmt).all()]
        except ProgrammingError as exc:
            self.db.rollback()
            logger.warning("search terms unavailable (migration missing?): %s", exc)
            return []

    # ── Aufmerksamkeit ──────────────────────────────────────────────────────
    def _attention(self, today: date, active) -> DashboardAttention:
        row = self.db.execute(
            select(
                func.coalesce(
                    func.sum(case((Document.is_unread.is_(True), 1), else_=0)), 0
                ).label("unread"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                or_(
                                    Document.ocr_quality_status.in_(("warning", "error")),
                                    Document.duplicate_of_doc_id.is_not(None),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("to_review"),
                func.coalesce(
                    func.sum(case((Document.ai_status.in_(("pending", "error")), 1), else_=0)), 0
                ).label("unclassified"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                or_(
                                    Document.text_source == "none",
                                    Document.ocr_quality_status.in_(("warning", "error")),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("ocr_issues"),
                func.coalesce(
                    func.sum(case((func.coalesce(func.trim(Document.document_type), "") == "", 1), else_=0)), 0
                ).label("without_document_type"),
            ).where(active)
        ).one()

        due_end = today + timedelta(days=RETENTION_DUE_WINDOW_DAYS)
        retention_due = int(
            self.db.scalar(
                select(func.count(Document.id))
                .join(DocumentRetention, DocumentRetention.document_id == Document.id)
                .where(
                    active,
                    DocumentRetention.retain_until.is_not(None),
                    DocumentRetention.retain_until >= today,
                    DocumentRetention.retain_until <= due_end,
                )
            )
            or 0
        )

        return DashboardAttention(
            unread=int(row.unread or 0),
            untagged=self._untagged_count(active),
            retention_due=retention_due,
            to_review=int(row.to_review or 0),
            unclassified=int(row.unclassified or 0),
            ocr_issues=int(row.ocr_issues or 0),
            without_document_type=int(row.without_document_type or 0),
        )

    # ── Zuletzt hinzugefügt ─────────────────────────────────────────────────
    def _recent(self, active, limit: int = 4) -> list[DashboardRecentItem]:
        rows = self.db.execute(
            select(
                Document.id,
                Document.display_name,
                Document.original_filename,
                Document.document_date,
                Document.created_at,
                Correspondent.name.label("correspondent"),
            )
            .outerjoin(Correspondent, Correspondent.id == Document.correspondent_id)
            .where(active)
            .order_by(Document.created_at.desc())
            .limit(limit)
        ).all()

        items: list[DashboardRecentItem] = []
        for row in rows:
            title = (row.display_name or row.original_filename or "").strip() or "Ohne Titel"
            when = row.document_date or row.created_at
            items.append(
                DashboardRecentItem(
                    id=str(row.id),
                    title=title,
                    correspondent=row.correspondent,
                    date=when.isoformat() if when else None,
                )
            )
        return items
