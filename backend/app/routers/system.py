from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.system import (
    PowerActionRequest,
    PowerActionResponse,
    ServiceActionResponse,
    ServiceStatusResponse,
    SystemStatus,
)
from app.services import system_status as service

# Systemmetriken und v. a. Power-Aktionen (Herunterfahren/Neustart) sind reine
# Admin-Funktionen.
router = APIRouter(prefix="/api/system", tags=["System"], dependencies=[Depends(require_admin)])


@router.get(
    "/status",
    response_model=SystemStatus,
    summary="Hardware-/Systemstatus des Hosts (Raspberry Pi)",
)
async def get_system_status() -> SystemStatus:
    return await service.collect_status()


@router.get(
    "/services",
    response_model=ServiceStatusResponse,
    summary="Status der PaperMind-Dienste",
)
async def get_service_status(db: Session = Depends(get_db)) -> ServiceStatusResponse:
    return await service.collect_service_status(db)


@router.post(
    "/services/{service_key}/actions/{action}",
    response_model=ServiceActionResponse,
    summary="Dienstaktion ausführen",
)
async def post_service_action(service_key: str, action: str, db: Session = Depends(get_db)) -> ServiceActionResponse:
    return await service.request_service_action(db, service_key, action)


@router.post(
    "/power",
    response_model=PowerActionResponse,
    summary="Host herunterfahren oder neu starten",
    responses={400: {"model": ErrorResponse}},
)
def post_power_action(payload: PowerActionRequest) -> PowerActionResponse:
    accepted, detail = service.request_power_action(payload.action)
    return PowerActionResponse(accepted=accepted, action=payload.action, detail=detail)
