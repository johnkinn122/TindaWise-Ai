import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.schemas.common import ORMModel

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
StoreName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
# Length is the strongest simple rule (NIST SP 800-63B): at least 10 characters, no forced symbols.
Password = Annotated[str, Field(min_length=10, max_length=128)]
RoleName = Literal["owner", "manager", "cashier"]


class _EmailNormalizer(BaseModel):
    @field_validator("email", mode="after", check_fields=False)
    @classmethod
    def lowercase(cls, value: str) -> str:
        return value.lower()


class SignupRequest(_EmailNormalizer):
    full_name: FullName
    email: EmailStr
    password: Password
    store_name: StoreName


class LoginRequest(_EmailNormalizer):
    email: EmailStr
    # No length rule on login: an old password that no longer meets the rule must still work.
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserRead(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str


class OrganizationRead(ORMModel):
    id: uuid.UUID
    name: str
    currency: str
    # IANA zone the app shows times in (and where each store day starts).
    timezone: str


class Me(BaseModel):
    user: UserRead
    organization: OrganizationRead
    role: RoleName


class SessionCreated(Me):
    """Returned once at sign-in. The token is never shown again; only its hash is stored."""

    token: str
    expires_at: datetime


class MemberCreate(_EmailNormalizer):
    full_name: FullName
    email: EmailStr
    role: Literal["manager", "cashier"]
    temporary_password: Password


class MemberRead(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: RoleName
    is_active: bool
    joined_at: datetime
