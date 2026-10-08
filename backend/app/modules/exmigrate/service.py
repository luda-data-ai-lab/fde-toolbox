from datetime import UTC, datetime
from typing import Any

from fastapi import UploadFile
from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.files.service import read_upload, store_bytes
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement
from app.modules.exmigrate import analyzer, erd, report_md, scripts
from app.modules.exmigrate.models import XlAnalysis, XlErdDraft
from app.modules.exmigrate.schemas import AnalysisOut, AnalysisSummary, Dialect, Erd, ErdOut

WORKBOOK_EXTENSIONS = {"xlsx", "xlsm"}


def _analyses(db: Session, ctx: TenantContext) -> TenantScopedRepository[XlAnalysis]:
    return TenantScopedRepository(db, ctx, XlAnalysis)


def _drafts(db: Session, ctx: TenantContext) -> TenantScopedRepository[XlErdDraft]:
    return TenantScopedRepository(db, ctx, XlErdDraft)


def draft_of(db: Session, ctx: TenantContext, analysis: XlAnalysis) -> XlErdDraft:
    row = db.scalars(_drafts(db, ctx).query().where(XlErdDraft.analysis_id == analysis.id)).first()
    if row is None:
        raise AppError(404, "not_found")
    return row


def summary(db: Session, ctx: TenantContext, a: XlAnalysis, out: type[AnalysisSummary] = AnalysisSummary) -> Any:
    report = analyzer.report_of(a.report)
    draft = db.scalars(_drafts(db, ctx).query().where(XlErdDraft.analysis_id == a.id)).first()
    extra: dict[str, Any] = {"report": report} if out is AnalysisOut else {}
    return out.model_validate(
        {
            "id": a.id,
            "engagement_id": a.engagement_id,
            "file_id": a.file_id,
            "filename": a.filename,
            "status": a.status,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
            "created_by": a.created_by,
            "sheets": len(report.sheets),
            "formula_count": report.formula_count,
            "erd_confirmed": bool(draft and draft.confirmed),
            **extra,
        }
    )


def list_query(ctx: TenantContext, db: Session, engagement_id: str | None) -> Select[XlAnalysis]:
    stmt = _analyses(db, ctx).query()
    if engagement_id:
        stmt = stmt.where(XlAnalysis.engagement_id == engagement_id)
    return stmt


@audited("exmigrate.analysis_create", "xl_analysis")
def create_analysis(ctx: TenantContext, db: Session, engagement_id: str, file: UploadFile) -> XlAnalysis:
    TenantScopedRepository(db, ctx, Engagement).ensure_ref(engagement_id, "engagement_id")
    name, data = read_upload(file, WORKBOOK_EXTENSIONS)
    report = analyzer.analyze_workbook(data)
    stored = store_bytes(ctx, db, name, data, "xl_analysis", None)
    analysis = _analyses(db, ctx).create(
        engagement_id=engagement_id, file_id=stored.id, filename=name, report=report.model_dump(mode="json")
    )
    stored.owner_id = analysis.id
    _drafts(db, ctx).create(analysis_id=analysis.id, erd=erd.draft_erd(report).model_dump(mode="json"))
    return analysis


@audited("exmigrate.analysis_delete", "xl_analysis")
def delete_analysis(ctx: TenantContext, db: Session, analysis: XlAnalysis) -> str:
    db.delete(analysis)
    return analysis.id


def erd_out(draft: XlErdDraft) -> ErdOut:
    model = Erd.model_validate(draft.erd)
    return ErdOut.model_validate(
        {
            "id": draft.id,
            "analysis_id": draft.analysis_id,
            "erd": model,
            "confirmed": draft.confirmed,
            "confirmed_at": draft.confirmed_at,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "created_by": draft.created_by,
            "issues": erd.erd_issues(model),
        }
    )


@audited("exmigrate.erd_update", "xl_erd_draft")
def update_erd(ctx: TenantContext, db: Session, draft: XlErdDraft, body: Erd) -> XlErdDraft:
    return _drafts(db, ctx).update(
        draft, erd=body.model_dump(mode="json"), confirmed=False, confirmed_at=None, confirmed_by=None
    )


@audited("exmigrate.erd_confirm", "xl_erd_draft")
def confirm_erd(ctx: TenantContext, db: Session, draft: XlErdDraft) -> XlErdDraft:
    issues = erd.erd_issues(Erd.model_validate(draft.erd))
    if issues:
        raise AppError(422, "erd_invalid", detail={"issues": issues[:50]})
    return _drafts(db, ctx).update(draft, confirmed=True, confirmed_at=datetime.now(UTC), confirmed_by=ctx.user_id)


def _record_export(ctx: TenantContext, db: Session, analysis: XlAnalysis, fmt: str) -> None:
    record(
        db,
        action="exmigrate.export",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="xl_analysis",
        target_id=analysis.id,
        detail={"format": fmt},
        ip=ctx.ip,
    )
    db.commit()


def export_report(ctx: TenantContext, db: Session, analysis: XlAnalysis) -> str:
    text = report_md.to_markdown(analyzer.report_of(analysis.report), analysis.filename)
    _record_export(ctx, db, analysis, "md")
    return text


def export_mermaid(ctx: TenantContext, db: Session, analysis: XlAnalysis) -> str:
    text = erd.to_mermaid(Erd.model_validate(draft_of(db, ctx, analysis).erd))
    _record_export(ctx, db, analysis, "mmd")
    return text


def _confirmed(db: Session, ctx: TenantContext, analysis: XlAnalysis) -> Erd:
    draft = draft_of(db, ctx, analysis)
    if not draft.confirmed:
        raise AppError(409, "erd_not_confirmed")
    return Erd.model_validate(draft.erd)


def export_ddl(ctx: TenantContext, db: Session, analysis: XlAnalysis, dialect: Dialect) -> str:
    return scripts.ddl(_confirmed(db, ctx, analysis), dialect, analysis.filename)


def export_scripts(ctx: TenantContext, db: Session, analysis: XlAnalysis, dialect: Dialect) -> bytes:
    data = scripts.scripts_zip(_confirmed(db, ctx, analysis), dialect, analysis.filename)
    _record_export(ctx, db, analysis, f"scripts:{dialect}")
    return data
