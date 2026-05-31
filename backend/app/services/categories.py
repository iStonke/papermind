import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.category import Category
from app.models.document import Document
from app.schemas.categories import CategoryCreateRequest, CategoryRead, CategoryUpdateRequest
from app.services.utils import is_unique_violation, normalize_name

logger = logging.getLogger("papermind.categories")


class CategoryService:
    def __init__(self, db: Session):
        self.db = db

    def list_categories(self, include_count: bool) -> list[CategoryRead]:
        if include_count:
            # Dokumente referenzieren die Kategorie denormalisiert über den Namen.
            stmt = (
                select(Category, func.count(Document.id).label("usage_count"))
                .outerjoin(
                    Document,
                    (Document.category == Category.name) & (Document.is_deleted.is_(False)),
                )
                .group_by(Category.id)
                .order_by(func.lower(Category.name).asc())
            )
            rows = self.db.execute(stmt).all()
            return [
                CategoryRead.model_validate(category, from_attributes=True).model_copy(
                    update={"usage_count": usage_count}
                )
                for category, usage_count in rows
            ]

        stmt = select(Category).order_by(func.lower(Category.name).asc())
        categories = self.db.execute(stmt).scalars().all()
        return [CategoryRead.model_validate(category, from_attributes=True) for category in categories]

    def _find_case_insensitive_name_conflict(
        self,
        category_name: str,
        *,
        exclude_category_id: uuid.UUID | None = None,
    ) -> Category | None:
        stmt = select(Category).where(func.lower(Category.name) == category_name.lower())
        if exclude_category_id is not None:
            stmt = stmt.where(Category.id != exclude_category_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_category(self, payload: CategoryCreateRequest) -> Category:
        category_name = normalize_name(payload.name)
        if not category_name:
            raise BadRequestError("Category name must not be empty")

        existing = self._find_case_insensitive_name_conflict(category_name)
        if existing is not None:
            return existing

        category = Category(name=category_name)
        self.db.add(category)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                existing = self._find_case_insensitive_name_conflict(category_name)
                if existing is not None:
                    return existing
                raise ConflictError("Category name already exists", details={"name": category_name}) from exc
            raise

        self.db.refresh(category)
        logger.info("category created id=%s", category.id)
        return category

    def get_category_or_404(self, category_id: uuid.UUID) -> Category:
        category = self.db.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found", details={"category_id": str(category_id)})
        return category

    def update_category(self, category_id: uuid.UUID, payload: CategoryUpdateRequest) -> Category:
        category = self.get_category_or_404(category_id)
        category_name = normalize_name(payload.name)
        if not category_name:
            raise BadRequestError("Category name must not be empty")

        if self._find_case_insensitive_name_conflict(category_name, exclude_category_id=category_id) is not None:
            raise ConflictError("Category name already exists", details={"name": category_name})

        old_name = category.name
        category.name = category_name

        try:
            # Denormalisierte Dokument-Referenzen mitziehen, damit nichts verwaist.
            if old_name != category_name:
                self.db.execute(
                    update(Document).where(Document.category == old_name).values(category=category_name)
                )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Category name already exists", details={"name": category_name}) from exc
            raise

        self.db.refresh(category)
        logger.info("category renamed id=%s old_name=%s new_name=%s", category.id, old_name, category.name)
        return category

    def delete_category(self, category_id: uuid.UUID) -> None:
        category = self.get_category_or_404(category_id)
        # Bewusst nicht-destruktiv: bereits zugewiesene Dokumente behalten ihren
        # Kategorie-Namen, nur das auswählbare Vokabular wird entfernt.
        self.db.delete(category)
        self.db.commit()
        logger.info("category deleted id=%s", category_id)
