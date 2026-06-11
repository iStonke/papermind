from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.sidebar import SidebarCountsResponse
from app.services.sidebar import SidebarService

router = APIRouter(prefix="/api/sidebar", tags=["Sidebar"])


@router.get(
    "/counts",
    response_model=SidebarCountsResponse,
    summary="Get aggregated sidebar counters",
)
def get_sidebar_counts(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SidebarCountsResponse:
    service = SidebarService(db, user.id)
    return service.get_counts()
