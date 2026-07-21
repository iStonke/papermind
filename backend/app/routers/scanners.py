import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.scanners import (
    ScanCommandRequest,
    ScanCommandResponse,
    ScannerDeviceCreateRequest,
    ScannerDeviceListResponse,
    ScannerDeviceRead,
    ScannerDeviceUpdateRequest,
)
from app.services.scanners import ScannerService

router = APIRouter(prefix="/api/scanners", tags=["Scanners"])


@router.get(
    "",
    response_model=ScannerDeviceListResponse,
    summary="List scanner devices (admin only)",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_scanners(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> ScannerDeviceListResponse:
    return ScannerService(db).list_devices()


@router.post(
    "",
    response_model=ScannerDeviceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create scanner device (admin only)",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_scanner(
    payload: ScannerDeviceCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScannerDeviceRead:
    return ScannerService(db).create_device(payload)


@router.post(
    "/{scanner_id}/scan",
    response_model=ScanCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a scan from the UI (page or finish)",
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def trigger_scan(
    scanner_id: uuid.UUID,
    payload: ScanCommandRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanCommandResponse:
    return ScannerService(db).enqueue_scan_command(scanner_id, payload.command, requested_by=user.id)


@router.post(
    "/{scanner_id}/cancel",
    response_model=ScanCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cancel active scanner work",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def cancel_scan(
    scanner_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanCommandResponse:
    return ScannerService(db).cancel_active_scan(scanner_id, requested_by=user.id)


@router.patch(
    "/{scanner_id}",
    response_model=ScannerDeviceRead,
    summary="Update scanner device and recipients (admin only)",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def update_scanner(
    scanner_id: uuid.UUID,
    payload: ScannerDeviceUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScannerDeviceRead:
    return ScannerService(db).update_device(scanner_id, payload)
