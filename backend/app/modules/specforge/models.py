from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

DOC_TYPES = ("spec", "devin")
DOC_STATUSES = ("draft", "confirmed")


class SpecDocument(TenantScopedModel):
    """Spec.md / Devin.md draft; `content_md` is the working copy, versions keep saved states."""

    __tablename__ = "spec_documents"

    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    template_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    rule_pack_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source_refs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SpecVersion(TenantScopedModel):
    __tablename__ = "spec_versions"
    __table_args__ = (UniqueConstraint("tenant_id", "document_id", "version", name="uq_spec_versions_doc_version"),)

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("spec_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
