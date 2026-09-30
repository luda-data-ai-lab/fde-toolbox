from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.auth.deps import DB, AdminPrincipal, CurrentPrincipal
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, WriteCtx, path_entity, repo
from app.modules.agenthub import service
from app.modules.agenthub.models import AgentEvalRun, AgentInstance
from app.modules.agenthub.schemas import (
    EvalCaseIn,
    EvalCaseOut,
    EvalCasePatch,
    EvalRunIn,
    EvalRunOut,
    InstanceIn,
    InstanceOut,
    InstancePatch,
    InstanceStatus,
)

asset_router = APIRouter(prefix="/assets", tags=["agenthub"])
router = APIRouter(prefix="/t/{tenant_id}/agenthub", tags=["agenthub"])

RunDep = Annotated[AgentEvalRun, Depends(path_entity(AgentEvalRun, "run_id"))]
InstanceDep = Annotated[AgentInstance, Depends(path_entity(AgentInstance, "instance_id"))]


@asset_router.get("/{asset_id}/versions/{version}/eval-cases", response_model=list[EvalCaseOut])
def list_cases(asset_id: str, version: int, principal: CurrentPrincipal, db: DB) -> list[EvalCaseOut]:
    return [EvalCaseOut.model_validate(c) for c in service.list_cases(db, asset_id, version)]


@asset_router.post("/{asset_id}/versions/{version}/eval-cases", response_model=EvalCaseOut, status_code=201)
def create_case(asset_id: str, version: int, body: EvalCaseIn, principal: AdminPrincipal, db: DB) -> EvalCaseOut:
    return EvalCaseOut.model_validate(service.create_case(principal, db, asset_id, version, body))


@asset_router.patch("/eval-cases/{case_id}", response_model=EvalCaseOut)
def update_case(case_id: str, body: EvalCasePatch, principal: AdminPrincipal, db: DB) -> EvalCaseOut:
    return EvalCaseOut.model_validate(service.update_case(principal, db, service.get_case(db, case_id), body))


@asset_router.delete("/eval-cases/{case_id}", status_code=204)
def delete_case(case_id: str, principal: AdminPrincipal, db: DB) -> Response:
    service.delete_case(principal, db, service.get_case(db, case_id))
    return Response(status_code=204)


@router.get("/eval-runs", response_model=Page[EvalRunOut])
def list_eval_runs(
    ctx: Ctx, db: DB, limit: int = 50, cursor: str | None = None, asset_id: str | None = None
) -> Page[EvalRunOut]:
    r = repo(db, ctx, AgentEvalRun)
    rows, nxt = r.page(limit=limit, cursor=cursor)
    items = [service.eval_run_out(x) for x in rows]
    if asset_id:
        items = [i for i in items if i.template_ref.asset_id == asset_id]
    return Page(items=items, next_cursor=nxt)


@router.post("/eval-runs", response_model=EvalRunOut, status_code=201)
def create_eval_run(body: EvalRunIn, ctx: WriteCtx, db: DB) -> EvalRunOut:
    return service.eval_run_out(service.create_eval_run(ctx, db, body))


@router.get("/eval-runs/{run_id}", response_model=EvalRunOut)
def get_eval_run(obj: RunDep) -> EvalRunOut:
    return service.eval_run_out(obj)


@router.delete("/eval-runs/{run_id}", status_code=204)
def delete_eval_run(obj: RunDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_eval_run(ctx, db, obj)
    return Response(status_code=204)


@router.get("/instances", response_model=Page[InstanceOut])
def list_instances(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    status: InstanceStatus | None = None,
    engagement_id: str | None = None,
) -> Page[InstanceOut]:
    r = repo(db, ctx, AgentInstance)
    stmt = r.query()
    if status:
        stmt = stmt.where(AgentInstance.status == status)
    if engagement_id:
        stmt = stmt.where(AgentInstance.engagement_id == engagement_id)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[InstanceOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/instances", response_model=InstanceOut, status_code=201)
def create_instance(body: InstanceIn, ctx: WriteCtx, db: DB) -> InstanceOut:
    return InstanceOut.model_validate(service.create_instance(ctx, db, body))


@router.get("/instances/{instance_id}", response_model=InstanceOut)
def get_instance(obj: InstanceDep) -> InstanceOut:
    return InstanceOut.model_validate(obj)


@router.patch("/instances/{instance_id}", response_model=InstanceOut)
def update_instance(obj: InstanceDep, body: InstancePatch, ctx: WriteCtx, db: DB) -> InstanceOut:
    return InstanceOut.model_validate(service.update_instance(ctx, db, obj, body))


@router.delete("/instances/{instance_id}", status_code=204)
def delete_instance(obj: InstanceDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_instance(ctx, db, obj)
    return Response(status_code=204)
