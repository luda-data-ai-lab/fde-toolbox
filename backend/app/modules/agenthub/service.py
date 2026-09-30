from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.assets.service import ref_exists
from app.core.audit.service import audited
from app.core.errors import AppError, not_found
from app.core.refs import ensure_tenant_ref, ensure_tenant_refs
from app.core.schemas import AssetRef
from app.core.tenancy.context import Principal, TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement
from app.core.users.service import user_has_tenant
from app.modules.agenthub.models import AgentEvalCase, AgentEvalRun, AgentInstance
from app.modules.agenthub.schemas import (
    EvalCaseIn,
    EvalCasePatch,
    EvalRunIn,
    EvalRunOut,
    InstanceIn,
    InstancePatch,
)

TEMPLATE_TYPE = "agent_template"


def ensure_template(db: Session, ref: AssetRef) -> None:
    if not ref_exists(db, ref.asset_id, ref.version, TEMPLATE_TYPE):
        raise AppError(422, "invalid_reference", detail={"field": "template_ref"})


def list_cases(db: Session, asset_id: str, version: int) -> list[AgentEvalCase]:
    if not ref_exists(db, asset_id, version, TEMPLATE_TYPE):
        raise not_found()
    return list(
        db.scalars(
            select(AgentEvalCase)
            .where(AgentEvalCase.asset_id == asset_id, AgentEvalCase.version == version)
            .order_by(AgentEvalCase.created_at, AgentEvalCase.id)
        )
    )


def get_case(db: Session, case_id: str) -> AgentEvalCase:
    case = db.get(AgentEvalCase, case_id)
    if case is None:
        raise not_found()
    return case


@audited("agenthub.eval_case_create", "agent_eval_case")
def create_case(ctx: Principal, db: Session, asset_id: str, version: int, body: EvalCaseIn) -> AgentEvalCase:
    if not ref_exists(db, asset_id, version, TEMPLATE_TYPE):
        raise not_found()
    case = AgentEvalCase(asset_id=asset_id, version=version, created_by=ctx.user_id, **body.model_dump())
    db.add(case)
    db.flush()
    return case


@audited("agenthub.eval_case_update", "agent_eval_case")
def update_case(ctx: Principal, db: Session, case: AgentEvalCase, body: EvalCasePatch) -> AgentEvalCase:
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        case.name = data["name"]
    if data.get("input") is not None:
        case.input = data["input"]
    if data.get("expected") is not None:
        case.expected = data["expected"]
    if "criteria" in data:
        case.criteria = data["criteria"]
    db.flush()
    return case


@audited("agenthub.eval_case_delete", "agent_eval_case")
def delete_case(ctx: Principal, db: Session, case: AgentEvalCase) -> str:
    db.delete(case)
    db.flush()
    return case.id


def eval_run_out(run: AgentEvalRun) -> EvalRunOut:
    out = EvalRunOut.model_validate(run)
    if out.results:
        out.pass_rate = round(sum(r.passed for r in out.results) / len(out.results), 4)
    return out


@audited("agenthub.eval_run_create", "agent_eval_run")
def create_eval_run(ctx: TenantContext, db: Session, body: EvalRunIn) -> AgentEvalRun:
    ensure_template(db, body.template_ref)
    case_ids = {c.id for c in list_cases(db, body.template_ref.asset_id, body.template_ref.version)}
    if any(r.case_id not in case_ids for r in body.results):
        raise AppError(422, "invalid_reference", detail={"field": "results.case_id"})
    ensure_tenant_refs(db, ctx, "files", body.evidence_file_ids, "evidence_file_ids")
    values: dict[str, Any] = body.model_dump(mode="json", exclude_none=True)
    if body.run_at is not None:
        values["run_at"] = body.run_at
    return TenantScopedRepository(db, ctx, AgentEvalRun).create(**values)


@audited("agenthub.eval_run_delete", "agent_eval_run")
def delete_eval_run(ctx: TenantContext, db: Session, run: AgentEvalRun) -> str:
    TenantScopedRepository(db, ctx, AgentEvalRun).delete(run)
    return run.id


def _check_instance_refs(db: Session, ctx: TenantContext, data: dict[str, Any]) -> None:
    if data.get("system_ids") is not None:
        ensure_tenant_refs(db, ctx, "systems", data["system_ids"], "system_ids")
    ensure_tenant_ref(db, ctx, "dev_projects", data.get("dev_project_id"), "dev_project_id")
    owner = data.get("owner_id")
    if owner is not None and not user_has_tenant(db, owner, ctx.tenant_id):
        raise AppError(422, "invalid_reference", detail={"field": "owner_id"})


@audited("agenthub.instance_create", "agent_instance")
def create_instance(ctx: TenantContext, db: Session, body: InstanceIn) -> AgentInstance:
    ensure_template(db, body.template_ref)
    TenantScopedRepository(db, ctx, Engagement).ensure_ref(body.engagement_id, "engagement_id")
    data = body.model_dump(mode="json")
    _check_instance_refs(db, ctx, data)
    return TenantScopedRepository(db, ctx, AgentInstance).create(**data)


@audited("agenthub.instance_update", "agent_instance")
def update_instance(ctx: TenantContext, db: Session, obj: AgentInstance, body: InstancePatch) -> AgentInstance:
    if body.template_ref is not None:
        ensure_template(db, body.template_ref)
    data = body.model_dump(mode="json", exclude_unset=True)
    _check_instance_refs(db, ctx, data)
    return TenantScopedRepository(db, ctx, AgentInstance).update(obj, **data)


@audited("agenthub.instance_delete", "agent_instance")
def delete_instance(ctx: TenantContext, db: Session, obj: AgentInstance) -> str:
    TenantScopedRepository(db, ctx, AgentInstance).delete(obj)
    return obj.id


def home_summary(ctx: TenantContext, db: Session) -> dict[str, Any]:
    counts: dict[str, int] = {
        str(k): int(v)
        for k, v in db.execute(
            select(AgentInstance.status, func.count())
            .where(AgentInstance.tenant_id == ctx.tenant_id)
            .group_by(AgentInstance.status)
        )
    }
    return {"instances_by_status": counts}
