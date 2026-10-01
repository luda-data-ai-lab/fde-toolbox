from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

LINK_TYPES = ("db_link", "api", "file", "mq", "eai", "other")
INTERFACE_STATUSES = ("planned", "developing", "operating", "retired")
UPLOAD_STATUSES = ("validated", "applied")


class Interface(TenantScopedModel):
    __tablename__ = "interfaces"
    __table_args__ = (UniqueConstraint("tenant_id", "if_code", name="uq_interfaces_tenant_if_code"),)

    if_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    source_system_id: Mapped[str] = mapped_column(String(36), ForeignKey("systems.id"), nullable=False, index=True)
    target_system_id: Mapped[str] = mapped_column(String(36), ForeignKey("systems.id"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="operating")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InterfaceUpload(TenantScopedModel):
    __tablename__ = "interface_uploads"

    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="validated")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
