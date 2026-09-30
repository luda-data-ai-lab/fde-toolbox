from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

Role = Literal["luda_admin", "fde", "client_admin", "client_user"]


class UserOut(ORMModel):
    email: str
    name: str
    role: str
    home_tenant_id: str | None
    is_active: bool


class UserIn(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$")
    name: str = Field(min_length=1, max_length=100)
    role: Role
    password: str = Field(min_length=8, max_length=200)
    home_tenant_id: str | None = None
    tenant_ids: list[str] = Field(default_factory=list)


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)
    home_tenant_id: str | None = None
    is_active: bool | None = None
    tenant_ids: list[str] | None = None


class UserAdminOut(UserOut):
    tenant_ids: list[str]
