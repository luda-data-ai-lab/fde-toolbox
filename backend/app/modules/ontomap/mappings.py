"""Data mappings (concept/attribute/relation → system, table/column, I/F) and per-concept coverage.

Interfaces and ExMigrate ERDs belong to other modules, so they are read by table name with an explicit tenant filter.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import Select, select, true
from sqlalchemy.orm import Session

from app.core.audit.service import audited
from app.core.errors import AppError
from app.core.refs import ensure_tenant_ref
from app.core.schemas import dump_patch
from app.core.systems.models import System
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.db.base import Base
from app.modules.ontomap.models import OntoAttribute, OntoConcept, OntoMapping, OntoRelation
from app.modules.ontomap.schemas import (
    CoverageRow,
    MappingIn,
    MappingPatch,
    MappingSources,
    SourceErdTable,
    SourceInterface,
    SourceSystem,
)


def _mappings(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoMapping]:
    return TenantScopedRepository(db, ctx, OntoMapping)


def mapping_filter(
    ctx: TenantContext, db: Session, *, concept_id: str | None, system_id: str | None
) -> Select[OntoMapping]:
    stmt = _mappings(db, ctx).query()
    if concept_id:
        stmt = stmt.where(OntoMapping.concept_id == concept_id)
    if system_id:
        stmt = stmt.where(OntoMapping.system_id == system_id)
    return stmt


def _owner(db: Session, ctx: TenantContext, kind: str, target_id: str) -> str:
    """Concept that owns the mapped target (the source concept for relations)."""
    owner: str | None = None
    if kind == "concept":
        concept = TenantScopedRepository(db, ctx, OntoConcept).get(target_id)
        owner = concept.id if concept else None
    elif kind == "attribute":
        attr = TenantScopedRepository(db, ctx, OntoAttribute).get(target_id)
        owner = attr.concept_id if attr else None
    else:
        rel = TenantScopedRepository(db, ctx, OntoRelation).get(target_id)
        owner = rel.source_concept_id if rel else None
    if owner is None:
        raise AppError(422, "invalid_reference", detail={"field": "target_id"})
    return owner


def _check(db: Session, ctx: TenantContext, kind: str, values: dict[str, Any]) -> None:
    ensure_tenant_ref(db, ctx, "systems", values.get("system_id"), "system_id")
    ensure_tenant_ref(db, ctx, "interfaces", values.get("interface_id"), "interface_id")
    missing: str | None = None
    if kind == "concept" and not values.get("system_id"):
        missing = "system_id"
    elif kind == "attribute" and not values.get("column_name"):
        missing = "column_name"
    elif (kind == "relation" and not (values.get("interface_id") or values.get("column_name"))) or (
        values.get("origin") == "interface" and not values.get("interface_id")
    ):
        missing = "interface_id"
    elif values.get("origin") == "exmigrate" and not values.get("table_name"):
        missing = "table_name"
    if missing:
        raise AppError(422, "mapping_incomplete", detail={"field": missing, "target_kind": kind})


def _clean(values: dict[str, Any]) -> dict[str, Any]:
    for key in ("table_name", "column_name", "notes"):
        if isinstance(values.get(key), str):
            values[key] = values[key].strip() or None
    return values


@audited("ontomap.mapping_create", "onto_mapping")
def create_mapping(ctx: TenantContext, db: Session, body: MappingIn) -> OntoMapping:
    return insert_mapping(db, ctx, body)


def insert_mapping(db: Session, ctx: TenantContext, body: MappingIn) -> OntoMapping:
    """Validated insert without its own audit/commit, for callers that write in one transaction."""
    values = _clean(body.model_dump())
    concept_id = _owner(db, ctx, body.target_kind, body.target_id)
    _check(db, ctx, body.target_kind, values)
    return _mappings(db, ctx).create(concept_id=concept_id, **values)


@audited("ontomap.mapping_update", "onto_mapping")
def update_mapping(ctx: TenantContext, db: Session, mapping: OntoMapping, body: MappingPatch) -> OntoMapping:
    values = _clean(dump_patch(body))
    if "origin" in values and values["origin"] is None:
        values.pop("origin")
    current = {
        "system_id": mapping.system_id,
        "table_name": mapping.table_name,
        "column_name": mapping.column_name,
        "interface_id": mapping.interface_id,
        "origin": mapping.origin,
    }
    merged = {key: values.get(key, value) for key, value in current.items()}
    _check(db, ctx, mapping.target_kind, merged)
    _mappings(db, ctx).update(mapping, **values)
    return mapping


@audited("ontomap.mapping_delete", "onto_mapping")
def delete_mapping(ctx: TenantContext, db: Session, mapping: OntoMapping) -> str:
    mapping_id = mapping.id
    _mappings(db, ctx).delete(mapping)
    return mapping_id


def coverage(db: Session, ctx: TenantContext) -> list[CoverageRow]:
    concepts = TenantScopedRepository(db, ctx, OntoConcept)
    attrs = TenantScopedRepository(db, ctx, OntoAttribute)
    systems = {s.id: s.name for s in TenantScopedRepository(db, ctx, System).all()}
    by_concept: dict[str, list[OntoMapping]] = defaultdict(list)
    for m in _mappings(db, ctx).all():
        by_concept[m.concept_id].append(m)
    attrs_by: dict[str, list[OntoAttribute]] = defaultdict(list)
    for a in attrs.all(attrs.query().order_by(OntoAttribute.created_at, OntoAttribute.id)):
        attrs_by[a.concept_id].append(a)
    rows: list[CoverageRow] = []
    for c in concepts.all(concepts.query().order_by(OntoConcept.name, OntoConcept.id)):
        ms = by_concept[c.id]
        mapped_attrs = {m.target_id for m in ms if m.target_kind == "attribute"}
        names = sorted({systems[m.system_id] for m in ms if m.system_id in systems})
        rows.append(
            CoverageRow(
                concept_id=c.id,
                name=c.name,
                status=c.status,
                mapping_count=len(ms),
                systems=names,
                attributes_total=len(attrs_by[c.id]),
                unmapped_attributes=[a.name for a in attrs_by[c.id] if a.id not in mapped_attrs],
            )
        )
    return rows


def sources(db: Session, ctx: TenantContext) -> MappingSources:
    tables = Base.metadata.tables
    ifs, drafts, analyses = tables["interfaces"], tables["xl_erd_drafts"], tables["xl_analyses"]
    sys_repo = TenantScopedRepository(db, ctx, System)
    systems = [SourceSystem(id=s.id, name=s.name) for s in sys_repo.all(sys_repo.query().order_by(System.name))]
    interfaces = [
        SourceInterface(id=r.id, if_code=r.if_code, name=r.name)
        for r in db.execute(
            select(ifs.c.id, ifs.c.if_code, ifs.c.name).where(ifs.c.tenant_id == ctx.tenant_id).order_by(ifs.c.if_code)
        )
    ]
    erd_tables: list[SourceErdTable] = []
    rows = db.execute(
        select(drafts.c.analysis_id, drafts.c.erd, analyses.c.filename)
        .join(analyses, analyses.c.id == drafts.c.analysis_id)
        .where(drafts.c.tenant_id == ctx.tenant_id, analyses.c.tenant_id == ctx.tenant_id, drafts.c.confirmed == true())
        .order_by(analyses.c.filename)
    )
    for r in rows:
        erd: dict[str, Any] = r.erd or {}
        for t in erd.get("tables", []):
            erd_tables.append(
                SourceErdTable(
                    analysis_id=r.analysis_id,
                    filename=r.filename,
                    table=str(t.get("name", "")),
                    label=str(t.get("label") or ""),
                    columns=[str(c.get("name", "")) for c in t.get("columns", [])],
                )
            )
    return MappingSources(systems=systems, interfaces=interfaces, erd_tables=erd_tables)
