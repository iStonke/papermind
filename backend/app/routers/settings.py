from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.settings import AppSettingsRead
from app.services.settings import SettingsService

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get(
    "",
    response_model=AppSettingsRead,
    summary="Get global application settings",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_settings(db: Session = Depends(get_db)) -> AppSettingsRead:
    service = SettingsService(db)
    return service.get_settings()


@router.put(
    "",
    response_model=AppSettingsRead,
    summary="Update global application settings",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def put_settings(payload: dict[str, Any] = Body(default_factory=dict), db: Session = Depends(get_db)) -> AppSettingsRead:
    service = SettingsService(db)
    return service.update_settings(payload)


@router.patch(
    "",
    response_model=AppSettingsRead,
    summary="Patch global application settings",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def patch_settings(payload: dict[str, Any] = Body(default_factory=dict), db: Session = Depends(get_db)) -> AppSettingsRead:
    service = SettingsService(db)
    return service.update_settings(payload)


@router.post(
    "/reset-prompts",
    response_model=AppSettingsRead,
    summary="Reset LLM prompts to system defaults",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def reset_prompts(db: Session = Depends(get_db)) -> AppSettingsRead:
    service = SettingsService(db)
    return service.reset_prompts()
