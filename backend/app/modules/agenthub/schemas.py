from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import AssetRef, ORMModel

InstanceStatus = Literal["ready", "pilot", "production", "stopped"]
DeploymentKind = Literal["standalone", "hosted", "customer_env"]


class EvalCaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    input: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    criteria: str | None = None


class EvalCasePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    input: str | None = Field(default=None, min_length=1)
    expected: str | None = Field(default=None, min_length=1)
    criteria: str | None = None


class EvalCaseOut(ORMModel):
    asset_id: str
    version: int
    name: str
    input: str
    expected: str
    criteria: str | None


class EvalResult(BaseModel):
    case_id: str
    passed: bool
    note: str | None = None


class EvalRunIn(BaseModel):
    template_ref: AssetRef
    run_at: datetime | None = None
    results: list[EvalResult] = Field(default_factory=list)
    evidence_file_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class EvalRunOut(ORMModel):
    tenant_id: str
    template_ref: AssetRef
    run_at: datetime
    results: list[EvalResult]
    evidence_file_ids: list[str]
    notes: str | None
    pass_rate: float | None = None


class InstanceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    template_ref: AssetRef
    engagement_id: str
    deployment: DeploymentKind = "standalone"
    system_ids: list[str] = Field(default_factory=list)
    overrides: dict[str, Any] = Field(default_factory=dict)
    status: InstanceStatus = "ready"
    owner_id: str | None = None
    dev_project_id: str | None = None
    notes: str | None = None


class InstancePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    template_ref: AssetRef | None = None
    deployment: DeploymentKind | None = None
    system_ids: list[str] | None = None
    overrides: dict[str, Any] | None = None
    status: InstanceStatus | None = None
    owner_id: str | None = None
    dev_project_id: str | None = None
    notes: str | None = None


class InstanceOut(ORMModel):
    tenant_id: str
    name: str
    template_ref: AssetRef
    engagement_id: str
    deployment: str
    system_ids: list[str]
    overrides: dict[str, Any]
    concept_bindings: dict[str, Any]
    status: str
    owner_id: str | None
    dev_project_id: str | None
    notes: str | None
