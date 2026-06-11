from pydantic import BaseModel, Field

from app.schemas.auth import UserRead


class UserListResponse(BaseModel):
    items: list[UserRead]


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=1024)
    display_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
    is_admin: bool = False


class UserUpdateRequest(BaseModel):
    """Field absent = unchanged; empty string for display_name/email = cleared."""

    password: str | None = Field(default=None, min_length=8, max_length=1024)
    display_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
    is_admin: bool | None = None
    is_active: bool | None = None
