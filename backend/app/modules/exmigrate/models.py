from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

ANALYSIS_STATUSES = ("analyzed",)


class XlAnalysis(TenantScopedModel):
    __tablename__ = "xl_analyses"

    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="analyzed")
    report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class XlErdDraft(TenantScopedModel):
    __tablename__ = "xl_erd_drafts"
    __table_args__ = (UniqueConstraint("tenant_id", "analysis_id", name="uq_xl_erd_drafts_tenant_analysis"),)

    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("xl_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    erd: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
