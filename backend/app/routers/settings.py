from typing import Any

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.notes import AICredentialsStatus, AIProviderCredentialUpdate
from app.schemas.settings import AppSettingsRead
from app.services.ai_credentials import AICredentialService
from app.services.settings import SettingsService

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get(
    "/ai-credentials",
    response_model=AICredentialsStatus,
    summary="Get masked note-AI credential status",
)
def get_ai_credentials(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AICredentialsStatus:
    try:
        return AICredentialService(db).status()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.put(
    "/ai-credentials",
    response_model=AICredentialsStatus,
    summary="Store an encrypted note-AI API key (admin only)",
)
def put_ai_credential(
    payload: AIProviderCredentialUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AICredentialsStatus:
    try:
        return AICredentialService(db).set_key(payload.provider, payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.delete(
    "/ai-credentials/{provider}",
    response_model=AICredentialsStatus,
    summary="Remove a stored note-AI API key (admin only)",
)
def delete_ai_credential(
    provider: Literal["openai", "anthropic"],
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AICredentialsStatus:
    try:
        return AICredentialService(db).delete_key(provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get(
    "",
    response_model=AppSettingsRead,
    summary="Get application settings (global + own UI preferences)",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AppSettingsRead:
    service = SettingsService(db, user.id)
    return service.get_settings()


@router.put(
    "",
    response_model=AppSettingsRead,
    summary="Update settings (UI per user; system settings require admin)",
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def put_settings(
    payload: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppSettingsRead:
    service = SettingsService(db, user.id)
    return service.apply_patch(payload, is_admin=user.is_admin)


@router.patch(
    "",
    response_model=AppSettingsRead,
    summary="Patch settings (UI per user; system settings require admin)",
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def patch_settings(
    payload: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppSettingsRead:
    service = SettingsService(db, user.id)
    return service.apply_patch(payload, is_admin=user.is_admin)


@router.post(
    "/reset-prompts",
    response_model=AppSettingsRead,
    summary="Reset LLM prompts to system defaults (admin only)",
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def reset_prompts(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> AppSettingsRead:
    service = SettingsService(db)
    return service.reset_prompts()
