from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
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


CONCEPT_STATUSES = ("draft", "confirmed", "deprecated")
DATA_TYPES = ("string", "integer", "decimal", "boolean", "date", "datetime", "code")
CARDINALITIES = ("1:1", "1:N", "N:M")


class OntoConcept(TenantScopedModel):
    """Customer concept; inherits either an upper-ontology concept (asset ref) or another customer concept."""

    __tablename__ = "onto_concepts"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    parent_concept_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("onto_concepts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    id_attribute_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner_dept: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)


class OntoAttribute(TenantScopedModel):
    __tablename__ = "onto_attributes"

    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("onto_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class OntoRelation(TenantScopedModel):
    __tablename__ = "onto_relations"

    source_concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("onto_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("onto_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cardinality: Mapped[str] = mapped_column(String(10), nullable=False, default="1:N")
    inverse_name: Mapped[str | None] = mapped_column(String(200), nullable=True)


MAPPING_KINDS = ("concept", "attribute", "relation")
MAPPING_ORIGINS = ("manual", "exmigrate", "interface")


class OntoMapping(TenantScopedModel):
    """Where a concept/attribute/relation lives (system + table/column, or an I/F); `concept_id` is its owner."""

    __tablename__ = "onto_mappings"

    target_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("onto_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    system_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("systems.id", ondelete="CASCADE"), nullable=True, index=True
    )
    table_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    column_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interface_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("interfaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
