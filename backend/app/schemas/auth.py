import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


class UserRead(ORMModel):
    id: uuid.UUID
    username: str
    display_name: str | None = None
    email: str | None = None
    is_admin: bool
    is_active: bool
    has_avatar: bool = False
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserRead


class FileTokenResponse(BaseModel):
    """Short-lived, file-scoped token for native resource loads (URL query)."""

    token: str
    expires_in: int


class RefreshTokenRequest(BaseModel):
    # Temporary migration path for browsers that still hold the former
    # localStorage refresh token. New clients use the HttpOnly cookie.
    refresh_token: str | None = Field(default=None, min_length=1, max_length=4096)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class ProfileUpdateRequest(BaseModel):
    """Self-service profile update. Field absent = unchanged; "" = cleared."""

    display_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
