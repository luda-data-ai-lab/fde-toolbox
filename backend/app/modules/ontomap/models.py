from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

TERM_STATUSES = ("candidate", "confirmed", "deprecated")
CANDIDATE_STATUSES = ("open", "accepted", "merged", "ignored")


class OntoTerm(TenantScopedModel):
    """Customer glossary term (tenant data; never written to global ontology assets)."""

    __tablename__ = "onto_terms"
    __table_args__ = (UniqueConstraint("tenant_id", "term", name="uq_onto_terms_tenant_term"),)

    term: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    abbreviation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed", index=True)
    concept_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class OntoTermAlias(TenantScopedModel):
    """Department-specific name for a term (e.g. 생산팀: 배합표)."""

    __tablename__ = "onto_term_aliases"

    term_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("onto_terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)


class OntoCandidate(TenantScopedModel):
    """Extracted or registered expression awaiting FDE review (accept / merge / ignore)."""

    __tablename__ = "onto_candidates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "kind", "source_type", "source_id", "name", name="uq_onto_candidates_tenant_source_name"
        ),
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="term")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    resolved_into_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
