from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.base import JsonScalar
from app.db.base import TenantScopedModel

ACTIVATION_STATUSES = ("requested", "active", "disabled")


class AdapterActivation(TenantScopedModel):
    """Per-tenant activation of an external-communication adapter (requested → approved → active)."""

    __tablename__ = "adapter_activations"
    __table_args__ = (UniqueConstraint("tenant_id", "adapter_key", name="uq_adapter_activations_tenant_key"),)

    adapter_key: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    config: Mapped[dict[str, JsonScalar]] = mapped_column(JSON, nullable=False, default=dict)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, info={"secret": True})
    egress_notice: Mapped[dict[str, str | list[str]]] = mapped_column(JSON, nullable=False, default=dict)
    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deactivated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
