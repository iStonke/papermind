from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.sidebar import SidebarCountsResponse
from app.services.sidebar import SidebarService

router = APIRouter(prefix="/api/sidebar", tags=["Sidebar"])


@router.get(
    "/counts",
    response_model=SidebarCountsResponse,
    summary="Get aggregated sidebar counters",
)
def get_sidebar_counts(db: Session = Depends(get_db)) -> SidebarCountsResponse:
    service = SidebarService(db)
    return service.get_counts()
