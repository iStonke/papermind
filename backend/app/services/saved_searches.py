import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.saved_search import SavedSearch
from app.schemas.saved_searches import SavedSearchCreateRequest, SavedSearchUpdateRequest
from app.services.utils import is_unique_violation, normalize_name

logger = logging.getLogger("papermind.saved_searches")


class SavedSearchService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def list_saved_searches(self) -> list[SavedSearch]:
        stmt = select(SavedSearch).order_by(func.lower(SavedSearch.name).asc(), SavedSearch.created_at.asc())
        if self.owner_id is not None:
            stmt = stmt.where(SavedSearch.owner_id == self.owner_id)
        return self.db.execute(stmt).scalars().all()

    def get_saved_search_or_404(self, saved_search_id: uuid.UUID) -> SavedSearch:
        saved_search = self.db.get(SavedSearch, saved_search_id)
        if saved_search is None or (
            self.owner_id is not None and saved_search.owner_id != self.owner_id
        ):
            raise NotFoundError("Smart folder not found", details={"saved_search_id": str(saved_search_id)})
        return saved_search

    def create_saved_search(self, payload: SavedSearchCreateRequest) -> SavedSearch:
        folder_name = normalize_name(payload.name)
        if not folder_name:
            raise BadRequestError("Smart folder name must not be empty")

        saved_search = SavedSearch(
            owner_id=self.owner_id,
            name=folder_name,
            query_json=payload.query.model_dump(mode="json", exclude_none=False),
        )
        self.db.add(saved_search)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Smart folder name already exists", details={"name": folder_name}) from exc
            raise

        self.db.refresh(saved_search)
        logger.info("smart folder created id=%s name=%s", saved_search.id, saved_search.name)
        return saved_search

    def update_saved_search(self, saved_search_id: uuid.UUID, payload: SavedSearchUpdateRequest) -> SavedSearch:
        saved_search = self.get_saved_search_or_404(saved_search_id)
        old_name = saved_search.name

        if payload.name is not None:
            folder_name = normalize_name(payload.name)
            if not folder_name:
                raise BadRequestError("Smart folder name must not be empty")
            saved_search.name = folder_name

        if payload.query is not None:
            saved_search.query_json = payload.query.model_dump(mode="json", exclude_none=False)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError(
                    "Smart folder name already exists",
                    details={"name": saved_search.name},
                ) from exc
            raise

        self.db.refresh(saved_search)
        logger.info("smart folder updated id=%s old_name=%s new_name=%s", saved_search.id, old_name, saved_search.name)
        return saved_search

    def delete_saved_search(self, saved_search_id: uuid.UUID) -> None:
        saved_search = self.get_saved_search_or_404(saved_search_id)
        self.db.delete(saved_search)
        self.db.commit()
        logger.info("smart folder deleted id=%s", saved_search_id)
