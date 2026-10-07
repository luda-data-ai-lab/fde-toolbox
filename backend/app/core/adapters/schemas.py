from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.base import FieldKind, JsonScalar

EffectiveStatus = Literal["requested", "active", "disabled"]


class EgressNoticeOut(BaseModel):
    destination: str
    data_kinds: list[str]
    features: list[str]


class ConfigFieldOut(BaseModel):
    name: str
    kind: FieldKind
    required: bool
    default: JsonScalar = None


class ActivationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    adapter_key: str
    status: EffectiveStatus
    config: dict[str, JsonScalar]
    has_credentials: bool
    egress_notice: EgressNoticeOut | None
    request_note: str | None
    requested_by: str | None
    requested_at: datetime | None
    approved_by: str | None
    approved_at: datetime | None
    approval_reason: str | None
    deactivated_by: str | None
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdapterOut(BaseModel):
    key: str
    display_name: str
    implemented: bool
    egress_notice: EgressNoticeOut
    config_fields: list[ConfigFieldOut]
    activation: ActivationOut | None


class ActivationRequestIn(BaseModel):
    adapter_key: str = Field(min_length=1, max_length=30)
    config: dict[str, JsonScalar] = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=1000)


class ApproveIn(BaseModel):
    acknowledged_egress: Literal[True]
    reason: str | None = Field(default=None, max_length=1000)


class ReasonIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class HealthOut(BaseModel):
    ok: bool
    message: str | None
    latency_ms: int
