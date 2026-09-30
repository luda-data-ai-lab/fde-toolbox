from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AssetModel, TenantScopedModel, utcnow

DEPLOYMENT_KINDS = ("standalone", "hosted", "customer_env")
INSTANCE_STATUSES = ("ready", "pilot", "production", "stopped")


class AgentEvalCase(AssetModel):
    """Evaluation case belonging to an agent template version (asset_id + version)."""

    __tablename__ = "agent_eval_cases"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentEvalRun(TenantScopedModel):
    __tablename__ = "agent_eval_runs"

    template_ref: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    evidence_file_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentInstance(TenantScopedModel):
    __tablename__ = "agent_instances"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_ref: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deployment: Mapped[str] = mapped_column(String(20), nullable=False, default="standalone")
    system_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    concept_bindings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dev_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
