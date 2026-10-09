"""Concept model: concepts, attributes, relations, upper-ontology inheritance and the validator.

Upper ontologies are global assets and are only read here; nothing in this module writes asset rows.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.assets.models import AssetItem
from app.core.audit.service import audited
from app.core.errors import AppError
from app.core.refs import ensure_tenant_ref
from app.core.schemas import dump_patch
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.modules.ontomap.models import OntoAttribute, OntoConcept, OntoRelation, OntoTerm
from app.modules.ontomap.schemas import (
    Ancestor,
    AttributeIn,
    AttributeOut,
    AttributePatch,
    ConceptDetail,
    ConceptIn,
    ConceptOut,
    ConceptPatch,
    InheritedProperty,
    InheritedRelation,
    RelationIn,
    RelationOut,
    RelationPatch,
    UpperConcept,
    UpperOntologyOut,
    UpperRef,
    UpperRelation,
    ValidationIssue,
)
from app.modules.ontomap.service import normalize, terms_out

UPPER_TYPE = "upper_ontology"


def _concepts(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoConcept]:
    return TenantScopedRepository(db, ctx, OntoConcept)


def _attributes(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoAttribute]:
    return TenantScopedRepository(db, ctx, OntoAttribute)


def _relations(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoRelation]:
    return TenantScopedRepository(db, ctx, OntoRelation)


# --- upper ontology (read-only assets) ----------------------------------------


def _upper(item: AssetItem) -> UpperOntologyOut:
    payload: dict[str, Any] = item.payload or {}
    concepts = [
        UpperConcept(
            key=str(c.get("concept_key") or c.get("key")),
            name=str(c.get("name") or c.get("label") or c.get("concept_key") or c.get("key")),
            definition=c.get("definition"),
            parent_key=c.get("parent_key"),
            iri_local=c.get("iri_local"),
            properties=[str(p.get("name") if isinstance(p, dict) else p) for p in c.get("properties", [])],
        )
        for c in payload.get("concepts", [])
        if c.get("concept_key") or c.get("key")
    ]
    relations = [
        UpperRelation(source=str(r["from"]), name=str(r.get("predicate") or r.get("name")), target=str(r["to"]))
        for r in payload.get("relations", [])
        if r.get("from") and r.get("to")
    ]
    return UpperOntologyOut(
        asset_id=item.asset_id,
        version=item.version,
        asset_key=item.asset_key,
        title=item.title,
        namespace=payload.get("namespace"),
        concepts=concepts,
        relations=relations,
    )


def list_upper(db: Session) -> list[UpperOntologyOut]:
    rows = db.scalars(
        select(AssetItem)
        .where(AssetItem.asset_type == UPPER_TYPE, AssetItem.status == "published")
        .order_by(AssetItem.title, AssetItem.version.desc())
    ).all()
    latest: dict[str, AssetItem] = {}
    for row in rows:
        latest.setdefault(row.asset_id, row)
    return [_upper(item) for item in latest.values()]


def _upper_version(db: Session, asset_id: str, version: int) -> UpperOntologyOut | None:
    item = db.scalars(
        select(AssetItem).where(
            AssetItem.asset_type == UPPER_TYPE,
            AssetItem.asset_id == asset_id,
            AssetItem.version == version,
            AssetItem.status != "draft",
        )
    ).first()
    return _upper(item) if item is not None else None


def _upper_concept(upper: UpperOntologyOut | None, key: str) -> UpperConcept | None:
    if upper is None:
        return None
    return next((c for c in upper.concepts if c.key == key), None)


# --- concepts -------------------------------------------------------------------


def concept_filter(ctx: TenantContext, db: Session, *, status: str | None, q: str | None) -> Select[OntoConcept]:
    stmt = _concepts(db, ctx).query()
    if status:
        stmt = stmt.where(OntoConcept.status == status)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(OntoConcept.name).like(like), func.lower(OntoConcept.definition).like(like)))
    return stmt


def _check_upper_ref(db: Session, ref: UpperRef) -> None:
    if _upper_concept(_upper_version(db, ref.asset_id, ref.version), ref.concept_key) is None:
        raise AppError(422, "invalid_reference", detail={"field": "parent_ref"})


def _check_parent_concept(db: Session, ctx: TenantContext, concept_id: str | None, parent_id: str) -> None:
    """Same tenant, and following the parent chain must never come back to ``concept_id``."""
    ensure_tenant_ref(db, ctx, "onto_concepts", parent_id, "parent_concept_id")
    parents = dict(
        db.execute(
            select(OntoConcept.id, OntoConcept.parent_concept_id).where(OntoConcept.tenant_id == ctx.tenant_id)
        ).all()
    )
    seen: set[str] = set()
    cur: str | None = parent_id
    while cur is not None and cur not in seen:
        if cur == concept_id:
            raise AppError(422, "inheritance_cycle", detail={"field": "parent_concept_id"})
        seen.add(cur)
        cur = parents.get(cur)


@audited("ontomap.concept_create", "onto_concept")
def create_concept(ctx: TenantContext, db: Session, body: ConceptIn) -> OntoConcept:
    if body.parent_ref is not None:
        _check_upper_ref(db, body.parent_ref)
    if body.parent_concept_id is not None:
        _check_parent_concept(db, ctx, None, body.parent_concept_id)
    values = body.model_dump(exclude={"parent_ref"})
    return _concepts(db, ctx).create(
        **values, parent_ref=body.parent_ref.model_dump() if body.parent_ref is not None else None
    )


@audited("ontomap.concept_update", "onto_concept")
def update_concept(ctx: TenantContext, db: Session, concept: OntoConcept, body: ConceptPatch) -> OntoConcept:
    values = dump_patch(body)
    for key in ("name", "status"):
        if key in values and values[key] is None:
            values.pop(key)
    if body.parent_ref is not None:
        _check_upper_ref(db, body.parent_ref)
        values["parent_ref"] = body.parent_ref.model_dump()
        values["parent_concept_id"] = None
    if body.parent_concept_id is not None:
        _check_parent_concept(db, ctx, concept.id, body.parent_concept_id)
        values["parent_ref"] = None
    if values.get("id_attribute_id") is not None:
        attr = _attributes(db, ctx).get(values["id_attribute_id"])
        if attr is None or attr.concept_id != concept.id:
            raise AppError(422, "invalid_reference", detail={"field": "id_attribute_id"})
    _concepts(db, ctx).update(concept, **values)
    return concept


@audited("ontomap.concept_delete", "onto_concept")
def delete_concept(ctx: TenantContext, db: Session, concept: OntoConcept) -> str:
    concept_id = concept.id
    db.execute(
        update(OntoTerm)
        .where(OntoTerm.tenant_id == ctx.tenant_id, OntoTerm.concept_id == concept_id)
        .values(concept_id=None)
    )
    _concepts(db, ctx).delete(concept)
    return concept_id


# --- attributes -------------------------------------------------------------------


@audited("ontomap.attribute_create", "onto_attribute")
def create_attribute(ctx: TenantContext, db: Session, concept: OntoConcept, body: AttributeIn) -> OntoAttribute:
    return _attributes(db, ctx).create(concept_id=concept.id, **body.model_dump())


@audited("ontomap.attribute_update", "onto_attribute")
def update_attribute(ctx: TenantContext, db: Session, attr: OntoAttribute, body: AttributePatch) -> OntoAttribute:
    values = {k: v for k, v in dump_patch(body).items() if v is not None or k == "unit"}
    _attributes(db, ctx).update(attr, **values)
    return attr


@audited("ontomap.attribute_delete", "onto_attribute")
def delete_attribute(ctx: TenantContext, db: Session, attr: OntoAttribute) -> str:
    attr_id = attr.id
    db.execute(
        update(OntoConcept)
        .where(OntoConcept.tenant_id == ctx.tenant_id, OntoConcept.id_attribute_id == attr_id)
        .values(id_attribute_id=None)
    )
    _attributes(db, ctx).delete(attr)
    return attr_id


# --- relations ---------------------------------------------------------------------


def relation_filter(ctx: TenantContext, db: Session, *, concept_id: str | None) -> Select[OntoRelation]:
    stmt = _relations(db, ctx).query()
    if concept_id:
        stmt = stmt.where(
            or_(OntoRelation.source_concept_id == concept_id, OntoRelation.target_concept_id == concept_id)
        )
    return stmt


@audited("ontomap.relation_create", "onto_relation")
def create_relation(ctx: TenantContext, db: Session, body: RelationIn) -> OntoRelation:
    ensure_tenant_ref(db, ctx, "onto_concepts", body.source_concept_id, "source_concept_id")
    ensure_tenant_ref(db, ctx, "onto_concepts", body.target_concept_id, "target_concept_id")
    return _relations(db, ctx).create(**body.model_dump())


@audited("ontomap.relation_update", "onto_relation")
def update_relation(ctx: TenantContext, db: Session, rel: OntoRelation, body: RelationPatch) -> OntoRelation:
    values = {k: v for k, v in dump_patch(body).items() if v is not None or k == "inverse_name"}
    if "target_concept_id" in values:
        ensure_tenant_ref(db, ctx, "onto_concepts", values["target_concept_id"], "target_concept_id")
    _relations(db, ctx).update(rel, **values)
    return rel


@audited("ontomap.relation_delete", "onto_relation")
def delete_relation(ctx: TenantContext, db: Session, rel: OntoRelation) -> str:
    rel_id = rel.id
    _relations(db, ctx).delete(rel)
    return rel_id


# --- inheritance + validation ------------------------------------------------------


def _ref(concept: OntoConcept) -> UpperRef | None:
    return UpperRef.model_validate(concept.parent_ref) if concept.parent_ref else None


def _upper_label(upper: UpperOntologyOut, c: UpperConcept) -> str:
    return f"{upper.title} v{upper.version} / {c.name}"


def concept_detail(db: Session, ctx: TenantContext, concept: OntoConcept) -> ConceptDetail:
    by_id = {c.id: c for c in _concepts(db, ctx).all()}
    attrs: dict[str, list[OntoAttribute]] = defaultdict(list)
    for a in _attributes(db, ctx).all(
        _attributes(db, ctx).query().order_by(OntoAttribute.created_at, OntoAttribute.id)
    ):
        attrs[a.concept_id].append(a)
    rels: dict[str, list[OntoRelation]] = defaultdict(list)
    all_rels = _relations(db, ctx).all(_relations(db, ctx).query().order_by(OntoRelation.created_at, OntoRelation.id))
    for r in all_rels:
        rels[r.source_concept_id].append(r)

    ancestors: list[Ancestor] = []
    props: list[InheritedProperty] = []
    inherited_rels: list[InheritedRelation] = []
    seen = {concept.id}
    cur = concept
    while cur.parent_concept_id and cur.parent_concept_id in by_id and cur.parent_concept_id not in seen:
        cur = by_id[cur.parent_concept_id]
        seen.add(cur.id)
        ancestors.append(Ancestor(kind="concept", id=cur.id, name=cur.name))
        props += [InheritedProperty(name=a.name, data_type=a.data_type, origin=cur.name) for a in attrs[cur.id]]
        inherited_rels += [
            InheritedRelation(name=r.name, target=by_id[r.target_concept_id].name, origin=cur.name)
            for r in rels[cur.id]
            if r.target_concept_id in by_id
        ]
    ref = _ref(cur)
    if ref is not None:
        upper = _upper_version(db, ref.asset_id, ref.version)
        if upper is not None:
            keys = {c.key: c for c in upper.concepts}
            key: str | None = ref.concept_key
            visited: set[str] = set()
            while key is not None and key in keys and key not in visited:
                visited.add(key)
                uc = keys[key]
                label = _upper_label(upper, uc)
                ancestors.append(
                    Ancestor(kind="upper", id=uc.key, name=uc.name, ontology=f"{upper.title} v{upper.version}")
                )
                props += [InheritedProperty(name=p, origin=label) for p in uc.properties]
                inherited_rels += [
                    InheritedRelation(
                        name=r.name, target=keys[r.target].name if r.target in keys else r.target, origin=label
                    )
                    for r in upper.relations
                    if r.source == uc.key
                ]
                key = uc.parent_key

    terms = _terms_for(db, ctx, concept.id)
    return ConceptDetail(
        **concept_out(concept).model_dump(),
        attributes=[AttributeOut.model_validate(a) for a in attrs[concept.id]],
        relations=[
            RelationOut.model_validate(r) for r in all_rels if concept.id in (r.source_concept_id, r.target_concept_id)
        ],
        ancestors=ancestors,
        inherited_properties=props,
        inherited_relations=inherited_rels,
        terms=terms_out(db, ctx, terms),
        warnings=[i for i in validate(db, ctx) if i.target_id == concept.id],
    )


def _terms_for(db: Session, ctx: TenantContext, concept_id: str) -> list[OntoTerm]:
    repo = TenantScopedRepository(db, ctx, OntoTerm)
    return repo.all(repo.query().where(OntoTerm.concept_id == concept_id).order_by(OntoTerm.term))


def concept_out(concept: OntoConcept) -> ConceptOut:
    return ConceptOut.model_validate(concept)


def validate(db: Session, ctx: TenantContext) -> list[ValidationIssue]:
    """Warnings only; saving is never blocked here (inheritance cycles are rejected on write)."""
    concepts = _concepts(db, ctx).all(_concepts(db, ctx).query().order_by(OntoConcept.name, OntoConcept.id))
    issues: list[ValidationIssue] = []
    by_name: dict[str, list[OntoConcept]] = defaultdict(list)
    uppers: dict[tuple[str, int], UpperOntologyOut | None] = {}
    for c in concepts:
        by_name[normalize(c.name)].append(c)
        ref = _ref(c)
        if ref is None and c.parent_concept_id is None:
            issues.append(
                ValidationIssue(code="orphan_concept", target_type="onto_concept", target_id=c.id, name=c.name)
            )
        elif ref is not None:
            k = (ref.asset_id, ref.version)
            if k not in uppers:
                uppers[k] = _upper_version(db, *k)
            if _upper_concept(uppers[k], ref.concept_key) is None:
                issues.append(
                    ValidationIssue(code="dangling_upper_ref", target_type="onto_concept", target_id=c.id, name=c.name)
                )
    for group in by_name.values():
        if len(group) > 1:
            issues += [
                ValidationIssue(code="duplicate_concept", target_type="onto_concept", target_id=c.id, name=c.name)
                for c in group
            ]
    repo = TenantScopedRepository(db, ctx, OntoTerm)
    for t in repo.all(
        repo.query()
        .where(OntoTerm.status == "confirmed", or_(OntoTerm.definition.is_(None), OntoTerm.definition == ""))
        .order_by(OntoTerm.term)
    ):
        issues.append(
            ValidationIssue(code="term_without_definition", target_type="onto_term", target_id=t.id, name=t.term)
        )
    return issues
