import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=1024)
    display_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)


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
    """Self-service profile update. Field absent = unchanged; "" = cleared.

    ``username`` is the login name: absent = unchanged, and (unlike the optional
    free-text fields) it may not be cleared to empty.
    """

    username: str | None = Field(default=None, min_length=1, max_length=150)
    display_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)


class StorageRoleUsage(BaseModel):
    bytes: int
    files: int


class StorageUsageResponse(BaseModel):
    """Owner-scoped storage footprint for the account data overview."""

    total_bytes: int
    document_count: int
    by_role: dict[str, StorageRoleUsage]


class DeleteAccountRequest(BaseModel):
    """Self-service account deletion: the current password re-confirms intent."""

    password: str = Field(min_length=1, max_length=1024)


class SessionRead(ORMModel):
    """One active browser/device session of the current user."""

    id: uuid.UUID
    user_agent: str | None = None
    client_ip: str | None = None
    created_at: datetime
    last_used_at: datetime
    current: bool = False
