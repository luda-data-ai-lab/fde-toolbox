from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.auth.deps import DB
from app.core.exports import attachment
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.specforge import service
from app.modules.specforge.models import SpecDocument, SpecVersion
from app.modules.specforge.schemas import (
    DiffOut,
    DocumentIn,
    DocumentOut,
    DocumentPatch,
    DocumentSummary,
    EnrichIn,
    EnrichOut,
    EnrichPromptOut,
    RulePackOut,
    TemplateOut,
    VersionIn,
    VersionOut,
    VersionSummary,
)

router = APIRouter(prefix="/t/{tenant_id}/specforge", tags=["specforge"])

DocDep = Annotated[SpecDocument, Depends(path_entity(SpecDocument, "document_id"))]
MD = "text/markdown; charset=utf-8"


@router.get("/templates", response_model=list[TemplateOut])
def templates(ctx: Ctx, db: DB) -> list[TemplateOut]:
    return service.list_templates(db)


@router.get("/rule-packs", response_model=list[RulePackOut])
def rule_packs(ctx: Ctx, db: DB) -> list[RulePackOut]:
    return service.list_rule_packs(db)


@router.get("/documents", response_model=Page[DocumentSummary])
def list_documents(
    ctx: Ctx, db: DB, limit: int = 100, cursor: str | None = None, engagement_id: str | None = None
) -> Page[DocumentSummary]:
    stmt = service.list_query(ctx, db, engagement_id)
    rows, nxt = repo(db, ctx, SpecDocument).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[service.summary_out(db, ctx, d) for d in rows], next_cursor=nxt)


@router.post("/documents", response_model=DocumentOut, status_code=201)
def create_document(body: DocumentIn, ctx: WriteCtx, db: DB) -> DocumentOut:
    return service.document_out(db, ctx, service.create_document(ctx, db, body))


@router.get("/documents/export.zip")
def export_zip(ctx: ExportCtx, db: DB, engagement_id: str | None = None) -> Response:
    return attachment(service.export_zip(ctx, db, engagement_id), "application/zip", "specforge.zip")


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(doc: DocDep, ctx: Ctx, db: DB) -> DocumentOut:
    return service.document_out(db, ctx, doc)


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document(doc: DocDep, body: DocumentPatch, ctx: WriteCtx, db: DB) -> DocumentOut:
    return service.document_out(db, ctx, service.update_document(ctx, db, doc, body))


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(doc: DocDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_document(ctx, db, doc)
    return Response(status_code=204)


@router.post("/documents/{document_id}/assemble", response_model=DocumentOut)
def reassemble(doc: DocDep, ctx: WriteCtx, db: DB) -> DocumentOut:
    return service.document_out(db, ctx, service.reassemble(ctx, db, doc))


@router.get("/documents/{document_id}/export.md")
def export_md(doc: DocDep, ctx: ExportCtx, db: DB) -> Response:
    text, name = service.export_markdown(ctx, db, doc)
    return attachment(text, MD, name)


@router.get("/documents/{document_id}/versions", response_model=list[VersionSummary])
def list_versions(doc: DocDep, ctx: Ctx, db: DB) -> list[SpecVersion]:
    return repo(db, ctx, SpecVersion).all(service.versions_query(db, ctx, doc))


@router.post("/documents/{document_id}/versions", response_model=VersionSummary, status_code=201)
def create_version(doc: DocDep, body: VersionIn, ctx: WriteCtx, db: DB) -> SpecVersion:
    return service.create_version(ctx, db, doc, body)


@router.get("/documents/{document_id}/versions/{version_id}", response_model=VersionOut)
def get_version(doc: DocDep, version_id: str, ctx: Ctx, db: DB) -> SpecVersion:
    return service.version_of(db, ctx, doc, version_id)


@router.post("/documents/{document_id}/versions/{version_id}/restore", response_model=DocumentOut)
def restore_version(doc: DocDep, version_id: str, ctx: WriteCtx, db: DB) -> DocumentOut:
    restored = service.restore_version(ctx, db, doc, service.version_of(db, ctx, doc, version_id))
    return service.document_out(db, ctx, restored)


@router.get("/documents/{document_id}/diff", response_model=DiffOut)
def diff(doc: DocDep, ctx: Ctx, db: DB, from_version: int = 1, to_version: int | None = None) -> DiffOut:
    return service.diff(db, ctx, doc, from_version, to_version)


@router.post("/documents/{document_id}/enrich-prompt", response_model=EnrichPromptOut)
def enrich_prompt(doc: DocDep, body: EnrichIn, ctx: WriteCtx, db: DB) -> EnrichPromptOut:
    return EnrichPromptOut(prompt=service.enrich_prompt(doc, body), llm_available=service.llm_available(ctx, db))


@router.post("/documents/{document_id}/enrich", response_model=EnrichOut)
def enrich(doc: DocDep, body: EnrichIn, ctx: WriteCtx, db: DB) -> EnrichOut:
    return EnrichOut(content_md=service.enrich(ctx, db, doc, body))
