from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.core.auth.deps import DB
from app.core.exports import attachment
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.exmigrate import service
from app.modules.exmigrate.models import XlAnalysis
from app.modules.exmigrate.schemas import AnalysisOut, AnalysisSummary, Dialect, Erd, ErdOut

router = APIRouter(prefix="/t/{tenant_id}/exmigrate", tags=["exmigrate"])

AnalysisDep = Annotated[XlAnalysis, Depends(path_entity(XlAnalysis, "analysis_id"))]


@router.get("/analyses", response_model=Page[AnalysisSummary])
def list_analyses(
    ctx: Ctx, db: DB, limit: int = 100, cursor: str | None = None, engagement_id: str | None = None
) -> Page[AnalysisSummary]:
    stmt = service.list_query(ctx, db, engagement_id)
    rows, nxt = repo(db, ctx, XlAnalysis).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[service.summary(db, ctx, a) for a in rows], next_cursor=nxt)


@router.post("/analyses", response_model=AnalysisOut, status_code=201)
def create_analysis(
    ctx: WriteCtx, db: DB, engagement_id: Annotated[str, Form()], file: Annotated[UploadFile, File()]
) -> AnalysisOut:
    a = service.create_analysis(ctx, db, engagement_id, file)
    out: AnalysisOut = service.summary(db, ctx, a, AnalysisOut)
    return out


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis: AnalysisDep, ctx: Ctx, db: DB) -> AnalysisOut:
    out: AnalysisOut = service.summary(db, ctx, analysis, AnalysisOut)
    return out


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis: AnalysisDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_analysis(ctx, db, analysis)
    return Response(status_code=204)


@router.get("/analyses/{analysis_id}/report.md")
def report_md(analysis: AnalysisDep, ctx: ExportCtx, db: DB) -> Response:
    return attachment(service.export_report(ctx, db, analysis), "text/markdown; charset=utf-8", "exmigrate-report.md")


@router.get("/analyses/{analysis_id}/erd", response_model=ErdOut)
def get_erd(analysis: AnalysisDep, ctx: Ctx, db: DB) -> ErdOut:
    return service.erd_out(service.draft_of(db, ctx, analysis))


@router.put("/analyses/{analysis_id}/erd", response_model=ErdOut)
def update_erd(analysis: AnalysisDep, body: Erd, ctx: WriteCtx, db: DB) -> ErdOut:
    return service.erd_out(service.update_erd(ctx, db, service.draft_of(db, ctx, analysis), body))


@router.post("/analyses/{analysis_id}/erd/confirm", response_model=ErdOut)
def confirm_erd(analysis: AnalysisDep, ctx: WriteCtx, db: DB) -> ErdOut:
    return service.erd_out(service.confirm_erd(ctx, db, service.draft_of(db, ctx, analysis)))


@router.get("/analyses/{analysis_id}/erd.mmd")
def erd_mermaid(analysis: AnalysisDep, ctx: ExportCtx, db: DB) -> Response:
    return attachment(service.export_mermaid(ctx, db, analysis), "text/plain; charset=utf-8", "erd.mmd")


@router.get("/analyses/{analysis_id}/ddl.sql")
def ddl(analysis: AnalysisDep, ctx: Ctx, db: DB, dialect: Dialect = "postgresql") -> Response:
    return Response(service.export_ddl(ctx, db, analysis, dialect), media_type="text/plain; charset=utf-8")


@router.get("/analyses/{analysis_id}/scripts.zip")
def scripts_zip(analysis: AnalysisDep, ctx: ExportCtx, db: DB, dialect: Dialect = "postgresql") -> Response:
    data = service.export_scripts(ctx, db, analysis, dialect)
    return attachment(data, "application/zip", f"exmigrate-{dialect}.zip")
