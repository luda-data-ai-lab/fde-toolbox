from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.auth.deps import DB
from app.core.exports import attachment
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.ontomap import service
from app.modules.ontomap.models import OntoCandidate, OntoTerm
from app.modules.ontomap.schemas import (
    AcceptIn,
    CandidateIn,
    CandidateOut,
    CandidateSource,
    CandidateStatus,
    ImportResult,
    MergeIn,
    TermIn,
    TermOut,
    TermPatch,
    TermStatus,
)

router = APIRouter(prefix="/t/{tenant_id}/ontomap", tags=["ontomap"])

TermDep = Annotated[OntoTerm, Depends(path_entity(OntoTerm, "term_id"))]
CandidateDep = Annotated[OntoCandidate, Depends(path_entity(OntoCandidate, "candidate_id"))]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _term_out(db: DB, ctx: Ctx, term: OntoTerm) -> TermOut:
    return service.terms_out(db, ctx, [term])[0]


def _candidate_out(db: DB, ctx: Ctx, candidate: OntoCandidate) -> CandidateOut:
    return service.candidates_out(db, ctx, [candidate])[0]


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
) -> Page[CandidateOut]:
    stmt = service.candidate_filter(ctx, db, status=status, source_type=source_type, source_id=source_id)
    rows, nxt = repo(db, ctx, OntoCandidate).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=service.candidates_out(db, ctx, rows), next_cursor=nxt)


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
    return _candidate_out(db, ctx, service.accept_candidate(ctx, db, candidate, body))


@router.post("/candidates/{candidate_id}/merge", response_model=CandidateOut)
def merge_candidate(candidate: CandidateDep, body: MergeIn, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, service.merge_candidate(ctx, db, candidate, body))


@router.post("/candidates/{candidate_id}/ignore", response_model=CandidateOut)
def ignore_candidate(candidate: CandidateDep, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, service.ignore_candidate(ctx, db, candidate))


@router.post("/candidates/{candidate_id}/reopen", response_model=CandidateOut)
def reopen_candidate(candidate: CandidateDep, ctx: WriteCtx, db: DB) -> CandidateOut:
    return _candidate_out(db, ctx, service.reopen_candidate(ctx, db, candidate))
