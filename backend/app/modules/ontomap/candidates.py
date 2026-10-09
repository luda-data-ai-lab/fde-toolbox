"""Candidate pipeline beyond glossary terms: rule-based extraction, concept/attribute/relation accept and merge,
merge suggestions per kind, and LLM suggestions (adapter or prompt-copy mode).

ERDs, I/Fs, flows and DiscoveryQ sessions belong to other modules, so they are read by table name with an
explicit tenant filter. Extractors and LLM answers only ever create `onto_candidates`.
"""

from collections import Counter

from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.adapters.base import AdapterDisabled
from app.adapters.registry import LLM, get_adapter, get_llm
from app.config import get_settings
from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.prompting import ResultParseError, build_json_prompt, parse_json_result
from app.core.refs import ensure_tenant_ref
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.db.base import Base
from app.modules.ontomap import extract, service
from app.modules.ontomap.mappings import insert_mapping
from app.modules.ontomap.models import OntoAttribute, OntoCandidate, OntoConcept, OntoRelation, OntoTerm
from app.modules.ontomap.schemas import (
    AcceptIn,
    CandidateOut,
    ExtractIn,
    ExtractResult,
    MappingIn,
    MappingOrigin,
    MergeIn,
    SimilarTerm,
    SuggestIn,
    SuggestPrompt,
    SuggestRun,
)

FEATURE = "ontomap.suggest"
CARDINALITIES = ("1:1", "1:N", "N:M")
MAX_PROMPT_ITEMS = 200
LANGUAGE = {"ko": "Korean", "en": "English"}


def _cands(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoCandidate]:
    return TenantScopedRepository(db, ctx, OntoCandidate)


def _concepts(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoConcept]:
    return TenantScopedRepository(db, ctx, OntoConcept)


# --- merge suggestions ----------------------------------------------------------------------


def _best(key: str, texts: list[str], threshold: int) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for text in texts:
        other = service.normalize(text)
        if not key or not other:
            continue
        score = 100 if key == other else round(fuzz.ratio(key, other))
        if score >= threshold and (best is None or score > best[0]):
            best = (score, text)
    return best


def _similar(name: str, labels: list[tuple[str, str, list[str]]]) -> list[SimilarTerm]:
    threshold = get_settings().onto_similarity_threshold
    key = service.normalize(name)
    hits = [
        SimilarTerm(term_id=target_id, term=display, matched=best[1], score=best[0])
        for target_id, display, texts in labels
        if (best := _best(key, texts, threshold)) is not None
    ]
    hits.sort(key=lambda h: (-h.score, h.term))
    return hits[: service.MAX_SIMILAR]


def candidates_out(db: Session, ctx: TenantContext, rows: list[OntoCandidate]) -> list[CandidateOut]:
    """Open candidates carry merge suggestions against existing items of the same kind (none for relations)."""
    open_rows = [c for c in rows if c.status == "open"]
    terms = service.similar_terms(db, ctx, [c.name for c in open_rows if c.kind == "term"])
    concept_labels: list[tuple[str, str, list[str]]] = []
    attr_labels: list[tuple[str, str, list[str]]] = []
    if any(c.kind in ("concept", "attribute") for c in open_rows):
        concepts = {c.id: c for c in _concepts(db, ctx).all()}
        concept_labels = [(c.id, c.name, [c.name]) for c in concepts.values()]
        attrs = TenantScopedRepository(db, ctx, OntoAttribute).all()
        attr_labels = [
            (a.id, extract.attribute_name(concepts[a.concept_id].name, a.name), [a.name])
            for a in attrs
            if a.concept_id in concepts
        ]
    out: list[CandidateOut] = []
    for c in rows:
        base = CandidateOut.model_validate(c)
        if c.status != "open":
            out.append(base)
            continue
        if c.kind == "term":
            similar = terms.get(c.name, [])
        elif c.kind == "concept":
            similar = _similar(c.name, concept_labels)
        elif c.kind == "attribute":
            similar = _similar(str(c.payload.get("attribute") or c.name), attr_labels)
        else:
            similar = []
        out.append(base.model_copy(update={"similar": similar}))
    return out


# --- registration / extraction --------------------------------------------------------------


def _register(
    db: Session,
    ctx: TenantContext,
    item: extract.Extracted,
    source_type: str,
    source_id: str | None,
) -> bool:
    """Idempotent per (kind, source, name): a candidate already seen — in any status — is not recreated."""
    repo = _cands(db, ctx)
    source_match = OntoCandidate.source_id.is_(None) if source_id is None else OntoCandidate.source_id == source_id
    existing = db.scalars(
        repo.query().where(
            OntoCandidate.kind == item.kind,
            OntoCandidate.source_type == source_type,
            source_match,
            OntoCandidate.name == item.name,
        )
    ).first()
    if existing is not None:
        return False
    repo.create(kind=item.kind, name=item.name, payload=item.payload, source_type=source_type, source_id=source_id)
    return True


def _erd_sources(db: Session, ctx: TenantContext, source_id: str | None) -> list[tuple[str, list[extract.Extracted]]]:
    tables = Base.metadata.tables
    drafts, analyses = tables["xl_erd_drafts"], tables["xl_analyses"]
    stmt = (
        select(drafts.c.analysis_id, drafts.c.erd, drafts.c.confirmed)
        .join(analyses, analyses.c.id == drafts.c.analysis_id)
        .where(drafts.c.tenant_id == ctx.tenant_id, analyses.c.tenant_id == ctx.tenant_id)
        .order_by(analyses.c.filename)
    )
    if source_id is not None:
        rows = db.execute(stmt.where(drafts.c.analysis_id == source_id)).all()
        if not rows:
            raise AppError(422, "invalid_reference", detail={"field": "source_id"})
        if not rows[0].confirmed:
            raise AppError(409, "erd_not_confirmed")
    else:
        rows = db.execute(stmt.where(drafts.c.confirmed == true())).all()
    return [(r.analysis_id, extract.from_erd(r.erd or {})) for r in rows]


def _interface_sources(
    db: Session, ctx: TenantContext, source_id: str | None
) -> list[tuple[str, list[extract.Extracted]]]:
    ifs = Base.metadata.tables["interfaces"]
    stmt = (
        select(ifs.c.id, ifs.c.if_code, ifs.c.name, ifs.c.description)
        .where(ifs.c.tenant_id == ctx.tenant_id)
        .order_by(ifs.c.if_code)
    )
    if source_id is not None:
        stmt = stmt.where(ifs.c.id == source_id)
    rows = db.execute(stmt).all()
    if source_id is not None and not rows:
        raise AppError(422, "invalid_reference", detail={"field": "source_id"})
    return [(r.id, extract.from_interface(r.name, r.if_code, r.description)) for r in rows]


def _flow_sources(db: Session, ctx: TenantContext, source_id: str | None) -> list[tuple[str, list[extract.Extracted]]]:
    flows = Base.metadata.tables["flows"]
    stmt = select(flows.c.id, flows.c.title, flows.c.graph).where(flows.c.tenant_id == ctx.tenant_id)
    if source_id is not None:
        stmt = stmt.where(flows.c.id == source_id)
    rows = db.execute(stmt.order_by(flows.c.title)).all()
    if source_id is not None and not rows:
        raise AppError(422, "invalid_reference", detail={"field": "source_id"})
    return [(r.id, extract.from_flow(r.title, r.graph or {})) for r in rows]


def _store(
    ctx: TenantContext, db: Session, groups: list[tuple[str | None, list[extract.Extracted]]], source_type: str
) -> ExtractResult:
    created, existing = 0, 0
    by_kind: Counter[str] = Counter()
    for source_id, items in groups:
        for item in items:
            if _register(db, ctx, item, source_type, source_id):
                created += 1
                by_kind[item.kind] += 1
            else:
                existing += 1
    return ExtractResult(created=created, existing=existing, by_kind=dict(by_kind))


def run_extract(ctx: TenantContext, db: Session, body: ExtractIn) -> ExtractResult:
    readers = {"exmigrate_erd": _erd_sources, "interface": _interface_sources, "flowdesk_flow": _flow_sources}
    groups: list[tuple[str | None, list[extract.Extracted]]] = list(readers[body.source_type](db, ctx, body.source_id))
    result = _store(ctx, db, groups, body.source_type)
    record(
        db,
        action="ontomap.candidate_extract",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type=body.source_type,
        target_id=body.source_id,
        detail=result.model_dump(),
        ip=ctx.ip,
    )
    db.commit()
    return result


# --- accept / merge -------------------------------------------------------------------------


def _origin(candidate: OntoCandidate) -> MappingOrigin:
    if candidate.source_type == "exmigrate_erd":
        return "exmigrate"
    if candidate.source_type == "interface":
        return "interface"
    return "manual"


def _concept_id(db: Session, ctx: TenantContext, given: str | None, field: str) -> str:
    if given is None or _concepts(db, ctx).get(given) is None:
        raise AppError(422, "invalid_reference", detail={"field": field})
    return given


def _resolve(db: Session, ctx: TenantContext, candidate: OntoCandidate, name: str | None) -> str | None:
    """Owning concept by name: the resolved sibling concept candidate from the same source, else an exact name."""
    if not name:
        return None
    repo = _cands(db, ctx)
    source_match = (
        OntoCandidate.source_id.is_(None)
        if candidate.source_id is None
        else OntoCandidate.source_id == candidate.source_id
    )
    sibling = db.scalars(
        repo.query().where(
            OntoCandidate.kind == "concept",
            OntoCandidate.source_type == candidate.source_type,
            source_match,
            OntoCandidate.name == name,
            OntoCandidate.resolved_into_id.is_not(None),
        )
    ).first()
    concepts = _concepts(db, ctx)
    if sibling is not None and sibling.resolved_into_id and concepts.get(sibling.resolved_into_id) is not None:
        return sibling.resolved_into_id
    match = db.scalars(concepts.query().where(OntoConcept.name == name).order_by(OntoConcept.created_at)).first()
    return match.id if match else None


def _owner(db: Session, ctx: TenantContext, candidate: OntoCandidate, given: str | None, key: str, field: str) -> str:
    if given is not None:
        return _concept_id(db, ctx, given, field)
    resolved = _resolve(db, ctx, candidate, candidate.payload.get(key))
    if resolved is None:
        raise AppError(422, "concept_required", detail={"field": field, "concept": candidate.payload.get(key)})
    return resolved


def _map_column(db: Session, ctx: TenantContext, candidate: OntoCandidate, kind: str, target_id: str) -> None:
    """ERD attribute/relation candidates carry their table and column, so accepting them records where they live."""
    column = candidate.payload.get("column")
    if candidate.source_type != "exmigrate_erd" or not column:
        return
    insert_mapping(
        db,
        ctx,
        MappingIn(
            target_kind="attribute" if kind == "attribute" else "relation",
            target_id=target_id,
            table_name=candidate.payload.get("table"),
            column_name=column,
            origin="exmigrate",
        ),
    )


def _accept_concept(db: Session, ctx: TenantContext, candidate: OntoCandidate, body: AcceptIn) -> str:
    if body.system_id is not None:
        ensure_tenant_ref(db, ctx, "systems", body.system_id, "system_id")
    concept = _concepts(db, ctx).create(
        name=body.term or candidate.name,
        definition=body.definition if body.definition is not None else candidate.payload.get("definition"),
        status="confirmed" if body.status == "confirmed" else "draft",
    )
    if body.system_id is not None:
        insert_mapping(
            db,
            ctx,
            MappingIn(
                target_kind="concept",
                target_id=concept.id,
                system_id=body.system_id,
                table_name=candidate.payload.get("table"),
                interface_id=candidate.source_id if candidate.source_type == "interface" else None,
                origin=_origin(candidate),
            ),
        )
    return concept.id


def _accept_attribute(db: Session, ctx: TenantContext, candidate: OntoCandidate, body: AcceptIn) -> str:
    concept_id = _owner(db, ctx, candidate, body.concept_id, "concept", "concept_id")
    data_type = candidate.payload.get("data_type", "string")
    attr = TenantScopedRepository(db, ctx, OntoAttribute).create(
        concept_id=concept_id,
        name=body.term or candidate.payload.get("attribute") or candidate.name,
        data_type=data_type,
        required=bool(candidate.payload.get("required", False)),
        constraints={},
    )
    _map_column(db, ctx, candidate, "attribute", attr.id)
    return attr.id


def _accept_relation(db: Session, ctx: TenantContext, candidate: OntoCandidate, body: AcceptIn) -> str:
    source = _owner(db, ctx, candidate, body.source_concept_id, "source", "source_concept_id")
    target = _owner(db, ctx, candidate, body.target_concept_id, "target", "target_concept_id")
    cardinality = candidate.payload.get("cardinality")
    rel = TenantScopedRepository(db, ctx, OntoRelation).create(
        source_concept_id=source,
        target_concept_id=target,
        name=body.term or candidate.payload.get("relation") or candidate.name,
        cardinality=cardinality if cardinality in CARDINALITIES else "1:N",
    )
    _map_column(db, ctx, candidate, "relation", rel.id)
    return rel.id


@audited("ontomap.candidate_accept", "onto_candidate")
def accept(ctx: TenantContext, db: Session, candidate: OntoCandidate, body: AcceptIn) -> OntoCandidate:
    if candidate.kind == "term":
        return service.accept_term_candidate(ctx, db, candidate, body)
    service.ensure_open(candidate)
    handlers = {"concept": _accept_concept, "attribute": _accept_attribute, "relation": _accept_relation}
    candidate.resolved_into_id = handlers[candidate.kind](db, ctx, candidate, body)
    candidate.status = "accepted"
    db.flush()
    return candidate


@audited("ontomap.candidate_merge", "onto_candidate")
def merge(ctx: TenantContext, db: Session, candidate: OntoCandidate, body: MergeIn) -> OntoCandidate:
    if candidate.kind == "term":
        return service.merge_term_candidate(ctx, db, candidate, body)
    service.ensure_open(candidate)
    models: dict[str, type[OntoConcept] | type[OntoAttribute] | type[OntoRelation]] = {
        "concept": OntoConcept,
        "attribute": OntoAttribute,
        "relation": OntoRelation,
    }
    target = TenantScopedRepository(db, ctx, models[candidate.kind]).get(body.target)
    if target is None:
        raise AppError(422, "invalid_reference", detail={"field": "target_id"})
    if isinstance(target, OntoConcept) and not target.definition and candidate.payload.get("definition"):
        target.definition = candidate.payload["definition"]
    if candidate.kind in ("attribute", "relation"):
        _map_column(db, ctx, candidate, candidate.kind, target.id)
    candidate.status = "merged"
    candidate.resolved_into_id = target.id
    db.flush()
    return candidate


# --- LLM suggestions ------------------------------------------------------------------------


class SuggestedTerm(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    definition: str | None = Field(default=None, max_length=2000)
    department: str | None = Field(default=None, max_length=100)
    context: str | None = Field(default=None, max_length=2000, description="Short quote where the term appears")


class SuggestedTerms(BaseModel):
    terms: list[SuggestedTerm] = Field(default_factory=list, max_length=100)


class SuggestedRelation(BaseModel):
    source: str = Field(min_length=1, max_length=200, description="Exact name of an existing concept")
    name: str = Field(min_length=1, max_length=200, description="Relation verb phrase")
    target: str = Field(min_length=1, max_length=200, description="Exact name of an existing concept")
    cardinality: str = Field(default="1:N", description="One of: 1:1, 1:N, N:M")


class SuggestedRelations(BaseModel):
    relations: list[SuggestedRelation] = Field(default_factory=list, max_length=100)


class SuggestedDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Exact name of a listed term or concept")
    definition: str = Field(min_length=1, max_length=2000)


class SuggestedDefinitions(BaseModel):
    definitions: list[SuggestedDefinition] = Field(default_factory=list, max_length=200)


SCHEMAS: dict[str, type[BaseModel]] = {
    "terms": SuggestedTerms,
    "relations": SuggestedRelations,
    "definitions": SuggestedDefinitions,
}


def _session_text(db: Session, ctx: TenantContext, session_id: str) -> str:
    tables = Base.metadata.tables
    sessions, questions, insights = (
        tables["discovery_sessions"],
        tables["discovery_session_questions"],
        tables["discovery_insights"],
    )
    session = db.execute(
        select(sessions.c.title, sessions.c.summary).where(
            sessions.c.tenant_id == ctx.tenant_id, sessions.c.id == session_id
        )
    ).first()
    if session is None:
        raise AppError(422, "invalid_reference", detail={"field": "session_id"})
    parts = [f"Interview: {session.title}"]
    if session.summary:
        parts.append(f"Summary: {session.summary}")
    qa = db.execute(
        select(questions.c.text, questions.c.answer)
        .where(questions.c.tenant_id == ctx.tenant_id, questions.c.session_id == session_id)
        .order_by(questions.c.position)
    ).all()
    parts += [f"Q: {q.text}\nA: {q.answer}" for q in qa if q.answer]
    notes: list[str] = list(
        db.scalars(
            select(insights.c.text).where(insights.c.tenant_id == ctx.tenant_id, insights.c.session_id == session_id)
        ).all()
    )
    parts += [f"Insight: {text}" for text in notes]
    return "\n\n".join(parts)


def _concept_line(c: OntoConcept) -> str:
    return f"- {c.name}: {c.definition}" if c.definition else f"- {c.name}"


def _prompt(db: Session, ctx: TenantContext, body: SuggestIn) -> str:
    lang = LANGUAGE[body.lang]
    if body.task == "terms":
        assert body.session_id is not None
        known = [t.term for t in TenantScopedRepository(db, ctx, OntoTerm).all()][:MAX_PROMPT_ITEMS]
        return "\n\n".join(
            [
                "You are an ontology analyst at a manufacturing customer. From the interview record below, extract"
                " business terms (documents, codes, objects, metrics) that the interviewees use.",
                "Interview record (DiscoveryQ):\n" + _session_text(db, ctx, body.session_id),
                "Already registered terms (do not repeat): " + (", ".join(known) or "(none)"),
                f"Write names, definitions and quotes in {lang}. Set `department` only when the record says which"
                " department uses the expression. Keep definitions to one sentence.",
            ]
        )
    concepts = [c for c in _concepts(db, ctx).all() if c.status != "deprecated"][:MAX_PROMPT_ITEMS]
    if body.task == "relations":
        if len(concepts) < 2:
            raise AppError(409, "not_enough_concepts")
        names = {c.id: c.name for c in concepts}
        rels = TenantScopedRepository(db, ctx, OntoRelation).all()
        existing = [
            f"- {names[r.source_concept_id]} -{r.name}-> {names[r.target_concept_id]}"
            for r in rels
            if r.source_concept_id in names and r.target_concept_id in names
        ]
        return "\n\n".join(
            [
                "You are an ontology analyst. Propose relations between the existing business concepts below.",
                "Concepts:\n"
                + "\n".join(f"- {c.name}" + (f": {c.definition}" if c.definition else "") for c in concepts),
                "Existing relations (do not repeat):\n" + ("\n".join(existing) or "(none)"),
                "Use only exact concept names from the list for `source` and `target`. Write relation names in"
                f" {lang} as a short verb phrase.",
            ]
        )
    terms = [t for t in TenantScopedRepository(db, ctx, OntoTerm).all() if not t.definition]
    undefined = [f"- term: {t.term}" for t in terms] + [f"- concept: {c.name}" for c in concepts if not c.definition]
    if not undefined:
        raise AppError(409, "nothing_to_define")
    return "\n\n".join(
        [
            "You are an ontology analyst at a manufacturing customer. Draft a one-sentence definition for each"
            " term or concept below.",
            "Items without a definition:\n" + "\n".join(undefined[:MAX_PROMPT_ITEMS]),
            f"Write definitions in {lang}. Use the exact item name in `name`; skip items you cannot define.",
        ]
    )


def llm_available(ctx: TenantContext, db: Session) -> bool:
    try:
        get_adapter(ctx, db, LLM.key)
    except AdapterDisabled:
        return False
    return True


def suggest_prompt(ctx: TenantContext, db: Session, body: SuggestIn) -> SuggestPrompt:
    prompt = build_json_prompt(_prompt(db, ctx, body), SCHEMAS[body.task])
    return SuggestPrompt(prompt=prompt, llm_available=llm_available(ctx, db))


def _items(db: Session, ctx: TenantContext, task: str, result: BaseModel) -> list[extract.Extracted]:
    out: list[extract.Extracted] = []
    if isinstance(result, SuggestedTerms):
        for t in result.terms:
            payload: extract.Payload = {
                k: v for k, v in t.model_dump(include={"definition", "department", "context"}).items() if v
            }
            out.append(extract.Extracted("term", " ".join(t.name.split()), {**payload, "task": task}))
        return out
    concepts = {service.normalize(c.name): c.name for c in _concepts(db, ctx).all()}
    if isinstance(result, SuggestedRelations):
        for r in result.relations:
            src, dst = concepts.get(service.normalize(r.source)), concepts.get(service.normalize(r.target))
            if src is None or dst is None:
                continue
            out.append(
                extract.Extracted(
                    "relation",
                    f"{src} —{r.name.strip()}→ {dst}"[: extract.MAX_NAME],
                    {
                        "source": src,
                        "target": dst,
                        "relation": r.name.strip(),
                        "cardinality": r.cardinality if r.cardinality in CARDINALITIES else "1:N",
                        "task": task,
                    },
                )
            )
        return out
    assert isinstance(result, SuggestedDefinitions)
    terms = {service.normalize(t.term): t.term for t in TenantScopedRepository(db, ctx, OntoTerm).all()}
    for d in result.definitions:
        key = service.normalize(d.name)
        if key in terms:
            out.append(extract.Extracted("term", terms[key], {"definition": d.definition.strip(), "task": task}))
        elif key in concepts:
            out.append(extract.Extracted("concept", concepts[key], {"definition": d.definition.strip(), "task": task}))
    return out


def suggest(ctx: TenantContext, db: Session, body: SuggestRun) -> ExtractResult:
    """Parse a pasted answer (copy mode) or call the LLM adapter; either way results become open candidates."""
    schema = SCHEMAS[body.task]
    prompt = _prompt(db, ctx, body)
    if body.answer is not None:
        mode = "copy"
        try:
            result = parse_json_result(body.answer, schema)
        except ResultParseError as exc:
            raise AppError(
                422, "suggest_result_invalid", detail={"reason": exc.reason, "errors": exc.errors[:20]}
            ) from exc
    else:
        mode = "llm"
        result = get_llm(ctx, db).generate_json(prompt, schema, feature=FEATURE)
    source_id = body.session_id if body.task == "terms" else None
    out = _store(ctx, db, [(source_id, _items(db, ctx, body.task, result))], "llm")
    record(
        db,
        action="ontomap.candidate_suggest",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="llm",
        target_id=source_id,
        detail={"mode": mode, "task": body.task, **out.model_dump()},
        ip=ctx.ip,
    )
    db.commit()
    return out
