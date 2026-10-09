from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.auth.deps import DB
from app.core.exports import attachment
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.ontomap import candidates, concepts, mappings, service
from app.modules.ontomap.models import OntoAttribute, OntoCandidate, OntoConcept, OntoMapping, OntoRelation, OntoTerm
from app.modules.ontomap.schemas import (
    AcceptIn,
    AttributeIn,
    AttributeOut,
    AttributePatch,
    CandidateIn,
    CandidateKind,
    CandidateOut,
    CandidateSource,
    CandidateStatus,
    ConceptDetail,
    ConceptIn,
    ConceptOut,
    ConceptPatch,
    ConceptStatus,
    CoverageRow,
    ExtractIn,
    ExtractResult,
    ImportResult,
    MappingIn,
    MappingOut,
    MappingPatch,
    MappingSources,
    MergeIn,
    RelationIn,
    RelationOut,
    RelationPatch,
    SuggestIn,
    SuggestPrompt,
    SuggestRun,
    TermIn,
    TermOut,
    TermPatch,
    TermStatus,
    UpperOntologyOut,
    ValidationReport,
)

router = APIRouter(prefix="/t/{tenant_id}/ontomap", tags=["ontomap"])

TermDep = Annotated[OntoTerm, Depends(path_entity(OntoTerm, "term_id"))]
CandidateDep = Annotated[OntoCandidate, Depends(path_entity(OntoCandidate, "candidate_id"))]
ConceptDep = Annotated[OntoConcept, Depends(path_entity(OntoConcept, "concept_id"))]
AttributeDep = Annotated[OntoAttribute, Depends(path_entity(OntoAttribute, "attribute_id"))]
RelationDep = Annotated[OntoRelation, Depends(path_entity(OntoRelation, "relation_id"))]
MappingDep = Annotated[OntoMapping, Depends(path_entity(OntoMapping, "mapping_id"))]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _term_out(db: DB, ctx: Ctx, term: OntoTerm) -> TermOut:
    return service.terms_out(db, ctx, [term])[0]


def _candidate_out(db: DB, ctx: Ctx, candidate: OntoCandidate) -> CandidateOut:
    return candidates.candidates_out(db, ctx, [candidate])[0]


@router.get("/terms", response_model=Page[TermOut])
def list_terms(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    status: TermStatus | None = None,
    q: str | None = None,
    department: str | None = None,
) -> Page[TermOut]:
    stmt = service.term_filter(ctx, db, status=status, q=q, department=department)
    rows, nxt = repo(db, ctx, OntoTerm).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=service.terms_out(db, ctx, rows), next_cursor=nxt)


@router.post("/terms", response_model=TermOut, status_code=201)
def create_term(body: TermIn, ctx: WriteCtx, db: DB) -> TermOut:
    return _term_out(db, ctx, service.create_term(ctx, db, body))


@router.get("/terms/template.xlsx")
def template(ctx: Ctx) -> Response:
    return attachment(service.template_workbook(), XLSX, "glossary-template.xlsx")


@router.get("/terms/export.xlsx")
def export_xlsx(ctx: ExportCtx, db: DB, status: TermStatus | None = None) -> Response:
    return attachment(service.export_workbook(ctx, db, status), XLSX, "glossary.xlsx")


@router.get("/terms/export.csv")
def export_csv(ctx: ExportCtx, db: DB, status: TermStatus | None = None) -> Response:
    return attachment(service.export_csv(ctx, db, status), "text/csv; charset=utf-8", "glossary.csv")


@router.post("/terms/import", response_model=ImportResult)
def import_terms(ctx: WriteCtx, db: DB, file: Annotated[UploadFile, File()], apply: bool = False) -> ImportResult:
    return service.import_workbook(ctx, db, file, apply)


@router.get("/terms/{term_id}", response_model=TermOut)
def get_term(term: TermDep, ctx: Ctx, db: DB) -> TermOut:
    return _term_out(db, ctx, term)


@router.patch("/terms/{term_id}", response_model=TermOut)
def update_term(term: TermDep, body: TermPatch, ctx: WriteCtx, db: DB) -> TermOut:
    return _term_out(db, ctx, service.update_term(ctx, db, term, body))


@router.delete("/terms/{term_id}", status_code=204)
def delete_term(term: TermDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_term(ctx, db, term)
    return Response(status_code=204)


@router.get("/candidates", response_model=Page[CandidateOut])
def list_candidates(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    status: CandidateStatus | None = None,
    source_type: CandidateSource | None = None,
    source_id: str | None = None,
    kind: CandidateKind | None = None,
) -> Page[CandidateOut]:
    stmt = service.candidate_filter(ctx, db, status=status, source_type=source_type, source_id=source_id, kind=kind)
    rows, nxt = repo(db, ctx, OntoCandidate).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=candidates.candidates_out(db, ctx, rows), next_cursor=nxt)


@router.post("/candidates/extract", response_model=ExtractResult)
def extract_candidates(body: ExtractIn, ctx: WriteCtx, db: DB) -> ExtractResult:
    return candidates.run_extract(ctx, db, body)


@router.post("/candidates/suggest/prompt", response_model=SuggestPrompt)
def suggest_prompt(body: SuggestIn, ctx: WriteCtx, db: DB) -> SuggestPrompt:
    return candidates.suggest_prompt(ctx, db, body)


@router.post("/candidates/suggest", response_model=ExtractResult)
def suggest_candidates(body: SuggestRun, ctx: WriteCtx, db: DB) -> ExtractResult:
    return candidates.suggest(ctx, db, body)


@router.post("/candidates", response_model=CandidateOut, status_code=201)
def register_candidate(body: CandidateIn, ctx: WriteCtx, db: DB, response: Response) -> CandidateOut:
    candidate, created = service.register_candidate(ctx, db, body)
    if not created:
        response.status_code = 200
    return _candidate_out(db, ctx, candidate)


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate: CandidateDep, ctx: Ctx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, candidate)


@router.post("/candidates/{candidate_id}/accept", response_model=CandidateOut)
def accept_candidate(candidate: CandidateDep, body: AcceptIn, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, candidates.accept(ctx, db, candidate, body))


@router.post("/candidates/{candidate_id}/merge", response_model=CandidateOut)
def merge_candidate(candidate: CandidateDep, body: MergeIn, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, candidates.merge(ctx, db, candidate, body))


@router.post("/candidates/{candidate_id}/ignore", response_model=CandidateOut)
def ignore_candidate(candidate: CandidateDep, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, service.ignore_candidate(ctx, db, candidate))


@router.post("/candidates/{candidate_id}/reopen", response_model=CandidateOut)
def reopen_candidate(candidate: CandidateDep, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, service.reopen_candidate(ctx, db, candidate))


@router.get("/upper-ontologies", response_model=list[UpperOntologyOut])
def list_upper_ontologies(ctx: Ctx, db: DB) -> list[UpperOntologyOut]:
    return concepts.list_upper(db)


@router.get("/concepts", response_model=Page[ConceptOut])
def list_concepts(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    status: ConceptStatus | None = None,
    q: str | None = None,
) -> Page[ConceptOut]:
    stmt = concepts.concept_filter(ctx, db, status=status, q=q)
    rows, nxt = repo(db, ctx, OntoConcept).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[concepts.concept_out(c) for c in rows], next_cursor=nxt)


@router.post("/concepts", response_model=ConceptDetail, status_code=201)
def create_concept(body: ConceptIn, ctx: WriteCtx, db: DB) -> ConceptDetail:
    return concepts.concept_detail(db, ctx, concepts.create_concept(ctx, db, body))


@router.get("/concepts/{concept_id}", response_model=ConceptDetail)
def get_concept(concept: ConceptDep, ctx: Ctx, db: DB) -> ConceptDetail:
    return concepts.concept_detail(db, ctx, concept)


@router.patch("/concepts/{concept_id}", response_model=ConceptDetail)
def update_concept(concept: ConceptDep, body: ConceptPatch, ctx: WriteCtx, db: DB) -> ConceptDetail:
    return concepts.concept_detail(db, ctx, concepts.update_concept(ctx, db, concept, body))


@router.delete("/concepts/{concept_id}", status_code=204)
def delete_concept(concept: ConceptDep, ctx: WriteCtx, db: DB) -> Response:
    concepts.delete_concept(ctx, db, concept)
    return Response(status_code=204)


@router.post("/concepts/{concept_id}/attributes", response_model=AttributeOut, status_code=201)
def create_attribute(concept: ConceptDep, body: AttributeIn, ctx: WriteCtx, db: DB) -> AttributeOut:
    return AttributeOut.model_validate(concepts.create_attribute(ctx, db, concept, body))


@router.patch("/attributes/{attribute_id}", response_model=AttributeOut)
def update_attribute(attr: AttributeDep, body: AttributePatch, ctx: WriteCtx, db: DB) -> AttributeOut:
    return AttributeOut.model_validate(concepts.update_attribute(ctx, db, attr, body))


@router.delete("/attributes/{attribute_id}", status_code=204)
def delete_attribute(attr: AttributeDep, ctx: WriteCtx, db: DB) -> Response:
    concepts.delete_attribute(ctx, db, attr)
    return Response(status_code=204)


@router.get("/relations", response_model=Page[RelationOut])
def list_relations(
    ctx: Ctx, db: DB, limit: int = 50, cursor: str | None = None, concept_id: str | None = None
) -> Page[RelationOut]:
    stmt = concepts.relation_filter(ctx, db, concept_id=concept_id)
    rows, nxt = repo(db, ctx, OntoRelation).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[RelationOut.model_validate(r) for r in rows], next_cursor=nxt)


@router.post("/relations", response_model=RelationOut, status_code=201)
def create_relation(body: RelationIn, ctx: WriteCtx, db: DB) -> RelationOut:
    return RelationOut.model_validate(concepts.create_relation(ctx, db, body))


@router.patch("/relations/{relation_id}", response_model=RelationOut)
def update_relation(rel: RelationDep, body: RelationPatch, ctx: WriteCtx, db: DB) -> RelationOut:
    return RelationOut.model_validate(concepts.update_relation(ctx, db, rel, body))


@router.delete("/relations/{relation_id}", status_code=204)
def delete_relation(rel: RelationDep, ctx: WriteCtx, db: DB) -> Response:
    concepts.delete_relation(ctx, db, rel)
    return Response(status_code=204)


@router.get("/validation", response_model=ValidationReport)
def validation(ctx: Ctx, db: DB) -> ValidationReport:
    return ValidationReport(issues=concepts.validate(db, ctx))


@router.get("/mappings", response_model=Page[MappingOut])
def list_mappings(
    ctx: Ctx,
    db: DB,
    limit: int = 200,
    cursor: str | None = None,
    concept_id: str | None = None,
    system_id: str | None = None,
) -> Page[MappingOut]:
    stmt = mappings.mapping_filter(ctx, db, concept_id=concept_id, system_id=system_id)
    rows, nxt = repo(db, ctx, OntoMapping).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[MappingOut.model_validate(m) for m in rows], next_cursor=nxt)


@router.post("/mappings", response_model=MappingOut, status_code=201)
def create_mapping(body: MappingIn, ctx: WriteCtx, db: DB) -> MappingOut:
    return MappingOut.model_validate(mappings.create_mapping(ctx, db, body))


@router.patch("/mappings/{mapping_id}", response_model=MappingOut)
def update_mapping(mapping: MappingDep, body: MappingPatch, ctx: WriteCtx, db: DB) -> MappingOut:
    return MappingOut.model_validate(mappings.update_mapping(ctx, db, mapping, body))


@router.delete("/mappings/{mapping_id}", status_code=204)
def delete_mapping(mapping: MappingDep, ctx: WriteCtx, db: DB) -> Response:
    mappings.delete_mapping(ctx, db, mapping)
    return Response(status_code=204)


@router.get("/mapping-sources", response_model=MappingSources)
def mapping_sources(ctx: Ctx, db: DB) -> MappingSources:
    return mappings.sources(db, ctx)


@router.get("/coverage", response_model=list[CoverageRow])
def coverage(ctx: Ctx, db: DB) -> list[CoverageRow]:
    return mappings.coverage(db, ctx)
