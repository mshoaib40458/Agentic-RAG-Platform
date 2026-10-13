"""Authentication and user schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import UserRole
from app.schemas.common import ORMModel

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class AuthConfig(BaseModel):
    auth_disabled: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.USER

    @field_validator("username")
    @classmethod
    def _valid_username(cls, value: str) -> str:
        if not _USERNAME_RE.match(value):
            raise ValueError("username may only contain letters, digits, '_', '.', '-'")
        return value

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value


class LoginRequest(BaseModel):
    username: str = Field(description="Username or email address")
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")


class UserRead(ORMModel):
    id: str
    email: EmailStr
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
