import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.document import Document
from app.models.smart_folder import SmartFolder
from app.schemas.documents import DocumentListResponse, DocumentSummary
from app.schemas.smart_folders import (
    SmartFolderCreateRequest,
    SmartFolderPreviewResponse,
    SmartFolderSort,
    SmartFolderUpdateRequest,
)
from app.services.smart_folder_query import SmartFolderQueryCompiler, build_smart_folder_sort, validate_smart_folder_query
from app.services.utils import is_unique_violation, normalize_name

logger = logging.getLogger("papermind.smart_folders")


class SmartFolderService:
    def __init__(self, db: Session):
        self.db = db
        self.compiler = SmartFolderQueryCompiler()

    def list_smart_folders(self) -> list[SmartFolder]:
        stmt = (
            select(SmartFolder)
            .order_by(SmartFolder.is_pinned.desc(), func.lower(SmartFolder.name).asc(), SmartFolder.created_at.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def get_smart_folder_or_404(self, smart_folder_id: uuid.UUID) -> SmartFolder:
        folder = self.db.get(SmartFolder, smart_folder_id)
        if folder is None:
            raise NotFoundError("Smart folder not found", details={"smart_folder_id": str(smart_folder_id)})
        return folder

    def create_smart_folder(self, payload: SmartFolderCreateRequest) -> SmartFolder:
        folder_name = normalize_name(payload.name)
        if not folder_name:
            raise BadRequestError("Smart folder name must not be empty")

        normalized_query = validate_smart_folder_query(payload.query_json)
        folder = SmartFolder(
            name=folder_name,
            is_pinned=bool(payload.is_pinned),
            query_json=normalized_query,
        )
        self.db.add(folder)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Smart folder name already exists", details={"name": folder_name}) from exc
            raise

        self.db.refresh(folder)
        logger.info("smart folder created id=%s name=%s", folder.id, folder.name)
        return folder

    def update_smart_folder(self, smart_folder_id: uuid.UUID, payload: SmartFolderUpdateRequest) -> SmartFolder:
        folder = self.get_smart_folder_or_404(smart_folder_id)
        old_name = folder.name

        if payload.name is not None:
            folder_name = normalize_name(payload.name)
            if not folder_name:
                raise BadRequestError("Smart folder name must not be empty")
            folder.name = folder_name

        if payload.is_pinned is not None:
            folder.is_pinned = bool(payload.is_pinned)

        if payload.query_json is not None:
            folder.query_json = validate_smart_folder_query(payload.query_json)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Smart folder name already exists", details={"name": folder.name}) from exc
            raise

        self.db.refresh(folder)
        logger.info("smart folder updated id=%s old_name=%s new_name=%s", folder.id, old_name, folder.name)
        return folder

    def delete_smart_folder(self, smart_folder_id: uuid.UUID) -> None:
        folder = self.get_smart_folder_or_404(smart_folder_id)
        self.db.delete(folder)
        self.db.commit()
        logger.info("smart folder deleted id=%s", smart_folder_id)

    def preview_documents(
        self,
        query_json: dict,
        *,
        count_only: bool = False,
        limit: int = 5,
        offset: int = 0,
        sort: SmartFolderSort = SmartFolderSort.created_desc,
    ) -> SmartFolderPreviewResponse:
        filter_expr = self.compiler.compile(query_json)
        if count_only:
            total_stmt = select(func.count()).select_from(select(Document.id).where(filter_expr).subquery())
            return SmartFolderPreviewResponse(total=int(self.db.scalar(total_stmt) or 0))

        list_response = self._list_documents(filter_expr, limit=limit, offset=offset, sort=sort)
        return SmartFolderPreviewResponse(
            total=list_response.total,
            items=list_response.items,
            limit=list_response.limit,
            offset=list_response.offset,
        )

    def list_folder_documents(
        self,
        smart_folder_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: SmartFolderSort = SmartFolderSort.created_desc,
    ) -> DocumentListResponse:
        folder = self.get_smart_folder_or_404(smart_folder_id)
        filter_expr = self.compiler.compile(folder.query_json)
        return self._list_documents(filter_expr, limit=limit, offset=offset, sort=sort)

    def count_documents_for_query(self, query_json: dict) -> int:
        filter_expr = self.compiler.compile(query_json)
        stmt = select(func.count()).select_from(select(Document.id).where(filter_expr).subquery())
        return int(self.db.scalar(stmt) or 0)

    def _list_documents(
        self,
        filter_expr,
        *,
        limit: int,
        offset: int,
        sort: SmartFolderSort,
    ) -> DocumentListResponse:
        order_exprs = build_smart_folder_sort(sort)

        filtered_stmt = select(Document).where(filter_expr)
        total_stmt = select(func.count()).select_from(filtered_stmt.order_by(None).subquery())
        total = int(self.db.scalar(total_stmt) or 0)

        items_stmt = (
            filtered_stmt.options(selectinload(Document.tags))
            .order_by(*order_exprs)
            .limit(limit)
            .offset(offset)
        )
        rows = self.db.execute(items_stmt).scalars().unique().all()
        items = [DocumentSummary.model_validate(item, from_attributes=True) for item in rows]
        for item, raw in zip(items, rows):
            item.is_duplicate = raw.duplicate_of_doc_id is not None

        return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)
