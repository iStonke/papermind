from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="Aggregated overview metrics for the dashboard",
)
def get_dashboard_overview(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DashboardOverviewResponse:
    service = DashboardService(db, user.id)
    return service.get_overview()
