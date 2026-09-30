from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

TenantStatus = Literal["active", "archived"]
DeploymentMode = Literal["standalone", "hosted"]
EngagementStatus = Literal["preparing", "in_progress", "on_hold", "completed"]


class TenantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    deployment_mode: DeploymentMode = "standalone"
    notes: str | None = None


class TenantPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: TenantStatus | None = None
    deployment_mode: DeploymentMode | None = None
    notes: str | None = None


class TenantOut(ORMModel):
    name: str
    code: str
    status: str
    deployment_mode: str
    notes: str | None


class EngagementIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    status: EngagementStatus = "preparing"
    start_date: date | None = None
    end_date: date | None = None
    lead_fde_id: str | None = None
    description: str | None = None


class EngagementPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: EngagementStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    lead_fde_id: str | None = None
    description: str | None = None


class EngagementOut(ORMModel):
    tenant_id: str
    name: str
    status: str
    start_date: date | None
    end_date: date | None
    lead_fde_id: str | None
    description: str | None
