import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_tag import document_tags
from app.models.saved_search import SavedSearch
from app.models.smart_folder import SmartFolder
from app.models.tag import Tag
from app.schemas.sidebar import SidebarCountsResponse, SidebarImportsCounts
from app.schemas.saved_searches import SavedSearchQuery
from app.services.smart_folder_query import SmartFolderQueryCompiler
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.sidebar")
settings = get_settings()


class SidebarService:
    def __init__(self, db: Session):
        self.db = db
        self.smart_folder_compiler = SmartFolderQueryCompiler()

    def _build_saved_search_conditions(self, raw_query: dict) -> list:
        query = SavedSearchQuery.model_validate(raw_query)
        conditions = []

        if query.tagId:
            tag_stmt = select(document_tags.c.document_id).where(document_tags.c.tag_id == query.tagId)
            conditions.append(Document.id.in_(tag_stmt))

        if query.status:
            conditions.append(Document.status == query.status.value)

        if query.dateFrom:
            conditions.append(Document.document_date >= query.dateFrom)

        if query.dateTo:
            conditions.append(Document.document_date <= query.dateTo)

        if query.q:
            ts_query = func.websearch_to_tsquery(settings.fts_regconfig, query.q)
            conditions.append(Document.search_vector.op("@@")(ts_query))

        return conditions

    def _saved_search_counts(self) -> dict[str, int]:
        saved_search_rows = self.db.execute(select(SavedSearch.id, SavedSearch.query_json)).all()
        if not saved_search_rows:
            return {}

        count_queries = []
        fallback_counts: dict[str, int] = {}
        for saved_search_id, query_json in saved_search_rows:
            try:
                conditions = self._build_saved_search_conditions(query_json or {})
                count_queries.append(
                    select(
                        literal(str(saved_search_id)).label("saved_search_id"),
                        func.count(Document.id).label("doc_count"),
                    )
                    .select_from(Document)
                    .where(Document.is_deleted.is_(False))
                    .where(*conditions)
                )
            except Exception as exc:
                logger.warning(
                    "saved search count skipped due to invalid query id=%s error=%s",
                    saved_search_id,
                    exc,
                )
                fallback_counts[str(saved_search_id)] = 0

        counts: dict[str, int] = {}
        if count_queries:
            union_stmt = union_all(*count_queries)
            for row in self.db.execute(union_stmt).all():
                counts[row.saved_search_id] = int(row.doc_count or 0)

        counts.update(fallback_counts)
        return counts

    def _smart_folder_counts(self) -> dict[str, int]:
        try:
            smart_folder_rows = self.db.execute(select(SmartFolder.id, SmartFolder.query_json)).all()
        except ProgrammingError as exc:
            self.db.rollback()
            logger.warning("smart folder counts unavailable (migration missing?): %s", exc)
            return {}
        if not smart_folder_rows:
            return {}

        count_queries = []
        fallback_counts: dict[str, int] = {}
        for smart_folder_id, query_json in smart_folder_rows:
            try:
                compiled_filter = self.smart_folder_compiler.compile(query_json or {})
                count_queries.append(
                    select(
                        literal(str(smart_folder_id)).label("smart_folder_id"),
                        func.count(Document.id).label("doc_count"),
                    )
                    .select_from(Document)
                    .where(Document.is_deleted.is_(False))
                    .where(compiled_filter)
                )
            except Exception as exc:
                logger.warning(
                    "smart folder count skipped due to invalid query id=%s error=%s",
                    smart_folder_id,
                    exc,
                )
                fallback_counts[str(smart_folder_id)] = 0

        counts: dict[str, int] = {}
        if count_queries:
            union_stmt = union_all(*count_queries)
            for row in self.db.execute(union_stmt).all():
                counts[row.smart_folder_id] = int(row.doc_count or 0)

        counts.update(fallback_counts)
        return counts

    def get_counts(self) -> SidebarCountsResponse:
        # Basis-Filter: nur nicht gelöschte Dokumente
        active_doc = Document.is_deleted.is_(False)

        try:
            totals_row = self.db.execute(
                select(
                    func.count(Document.id).label("all_documents"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Document.is_unread.is_(True), 1),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("unread_total"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Document.is_favorite.is_(True), 1),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("favorites_count"),
                ).where(active_doc)
            ).one()
            all_documents = int(totals_row.all_documents or 0)
            unread_total = int(totals_row.unread_total or 0)
            favorites_count = int(totals_row.favorites_count or 0)
        except ProgrammingError as exc:
            self.db.rollback()
            logger.warning("sidebar count fallback used: %s", exc)
            all_documents = int(self.db.scalar(select(func.count(Document.id)).where(active_doc)) or 0)
            unread_total = 0
            favorites_count = 0

        trash_count = int(
            self.db.scalar(select(func.count(Document.id)).where(Document.is_deleted.is_(True))) or 0
        )

        imports_row_map = {
            row.status: int(row.doc_count or 0)
            for row in self.db.execute(
                select(Document.status, func.count(Document.id).label("doc_count"))
                .where(active_doc)
                .where(Document.status.in_(("imported", "processing", "ready", "failed")))
                .group_by(Document.status)
            ).all()
        }
        runtime_settings = SettingsService(self.db).get_settings()
        recent_window_hours = max(1, int(runtime_settings.documents.recent_import_window_hours))
        recent_threshold = datetime.now(timezone.utc) - timedelta(hours=recent_window_hours)
        recent_total = int(
            self.db.scalar(
                select(func.count(Document.id))
                .where(active_doc)
                .where(Document.created_at >= recent_threshold)
            )
            or 0
        )
        imports = SidebarImportsCounts(
            imported=imports_row_map.get("imported", 0),
            processing=imports_row_map.get("processing", 0),
            ready=imports_row_map.get("ready", 0),
            failed=imports_row_map.get("failed", 0),
            recent_total=recent_total,
        )

        untagged_stmt = select(func.count(Document.id)).where(
            active_doc,
            ~select(document_tags.c.document_id)
            .where(document_tags.c.document_id == Document.id)
            .exists(),
        )
        untagged_count = int(self.db.scalar(untagged_stmt) or 0)

        tag_counts = {
            str(row.tag_id): int(row.doc_count or 0)
            for row in self.db.execute(
                select(document_tags.c.tag_id, func.count(Document.id).label("doc_count"))
                .join(Document, Document.id == document_tags.c.document_id)
                .where(active_doc)
                .group_by(document_tags.c.tag_id)
            ).all()
        }
        tags_total = int(
            self.db.scalar(
                select(func.count(func.distinct(document_tags.c.tag_id)))
                .select_from(document_tags)
                .join(Document, Document.id == document_tags.c.document_id)
                .where(active_doc)
            )
            or 0
        )

        smart_folder_counts = self._smart_folder_counts()
        saved_search_counts = self._saved_search_counts()
        if smart_folder_counts:
            # Keep legacy key for older clients while new clients use smart_folders.
            saved_search_counts = dict(smart_folder_counts)

        return SidebarCountsResponse(
            all_documents=all_documents,
            untagged=untagged_count,
            unread_total=unread_total,
            tags_total=tags_total,
            favorites_count=favorites_count,
            trash_count=trash_count,
            imports=imports,
            tags=tag_counts,
            smart_folders=smart_folder_counts,
            saved_searches=saved_search_counts,
        )
