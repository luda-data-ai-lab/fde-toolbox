from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

SystemType = Literal["MES", "ERP", "LIMS", "WMS", "SCADA", "GROUPWARE", "OTHER"]
Hosting = Literal["on_premise", "cloud"]


class SystemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    short_name: str | None = Field(default=None, max_length=50)
    type: SystemType = "OTHER"
    owner_dept: str | None = Field(default=None, max_length=100)
    hosting: Hosting | None = None
    db_type: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class SystemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    short_name: str | None = Field(default=None, max_length=50)
    type: SystemType | None = None
    owner_dept: str | None = Field(default=None, max_length=100)
    hosting: Hosting | None = None
    db_type: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class SystemOut(ORMModel):
    tenant_id: str
    name: str
    short_name: str | None
    type: str
    owner_dept: str | None
    hosting: str | None
    db_type: str | None
    notes: str | None
