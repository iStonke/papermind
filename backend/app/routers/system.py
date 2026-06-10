from fastapi import APIRouter, Depends

from app.core.deps import require_admin
from app.schemas.common import ErrorResponse
from app.schemas.system import PowerActionRequest, PowerActionResponse, SystemStatus
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


@router.post(
    "/power",
    response_model=PowerActionResponse,
    summary="Host herunterfahren oder neu starten",
    responses={400: {"model": ErrorResponse}},
)
def post_power_action(payload: PowerActionRequest) -> PowerActionResponse:
    accepted, detail = service.request_power_action(payload.action)
    return PowerActionResponse(accepted=accepted, action=payload.action, detail=detail)
