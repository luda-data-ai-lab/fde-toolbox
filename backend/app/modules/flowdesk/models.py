from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

FLOW_KINDS = ("as_is", "to_be")
PERSPECTIVES = ("business", "pm", "developer", "executive", "consultant")


class Flow(TenantScopedModel):
    """Business flow canvas; `graph` is the working copy, snapshots keep saved versions."""

    __tablename__ = "flows"

    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="as_is")
    pair_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    perspective: Mapped[str] = mapped_column(String(20), nullable=False, default="business")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class FlowSnapshot(TenantScopedModel):
    __tablename__ = "flow_snapshots"

    flow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
