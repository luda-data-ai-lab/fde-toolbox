from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.auth.deps import DB
from app.core.exports import attachment
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.flowdesk import service
from app.modules.flowdesk.models import Flow
from app.modules.flowdesk.schemas import (
    FlowIn,
    FlowKind,
    FlowOut,
    FlowPatch,
    FlowSummary,
    ImportIn,
    PairIn,
    SnapshotIn,
    SnapshotOut,
    SnapshotSummary,
    TemplateOut,
)

router = APIRouter(prefix="/t/{tenant_id}/flowdesk", tags=["flowdesk"])

FlowDep = Annotated[Flow, Depends(path_entity(Flow, "flow_id"))]


@router.get("/templates", response_model=list[TemplateOut])
def templates(ctx: Ctx, db: DB) -> list[TemplateOut]:
    return service.list_templates(db)


@router.get("/flows", response_model=Page[FlowSummary])
def list_flows(
    ctx: Ctx,
    db: DB,
    limit: int = 100,
    cursor: str | None = None,
    engagement_id: str | None = None,
    kind: FlowKind | None = None,
) -> Page[FlowSummary]:
    r = repo(db, ctx, Flow)
    stmt = r.query()
    if engagement_id:
        stmt = stmt.where(Flow.engagement_id == engagement_id)
    if kind:
        stmt = stmt.where(Flow.kind == kind)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[service.summary_out(x) for x in rows], next_cursor=nxt)


@router.post("/flows", response_model=FlowOut, status_code=201)
def create_flow(body: FlowIn, ctx: WriteCtx, db: DB) -> FlowOut:
    return service.flow_out(service.create_flow(ctx, db, body))


@router.post("/flows/import", response_model=FlowOut, status_code=201)
def import_flow(body: ImportIn, ctx: WriteCtx, db: DB) -> FlowOut:
    return service.flow_out(service.import_flow(ctx, db, body))


@router.get("/flows/{flow_id}", response_model=FlowOut)
def get_flow(flow: FlowDep, ctx: Ctx) -> FlowOut:
    return service.flow_out(flow)


@router.patch("/flows/{flow_id}", response_model=FlowOut)
def update_flow(flow: FlowDep, body: FlowPatch, ctx: WriteCtx, db: DB) -> FlowOut:
    return service.flow_out(service.update_flow(ctx, db, flow, body))


@router.delete("/flows/{flow_id}", status_code=204)
def delete_flow(flow: FlowDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_flow(ctx, db, flow)
    return Response(status_code=204)


@router.get("/flows/{flow_id}/pair", response_model=FlowOut)
def get_pair(flow: FlowDep, ctx: Ctx, db: DB) -> FlowOut:
    return service.flow_out(service.pair_of(db, ctx, flow))


@router.post("/flows/{flow_id}/pair", response_model=FlowOut, status_code=201)
def pair_flow(flow: FlowDep, body: PairIn, ctx: WriteCtx, db: DB) -> FlowOut:
    return service.flow_out(service.pair_flow(ctx, db, flow, body))


@router.delete("/flows/{flow_id}/pair", response_model=FlowOut)
def unpair_flow(flow: FlowDep, ctx: WriteCtx, db: DB) -> FlowOut:
    return service.flow_out(service.unpair_flow(ctx, db, flow))


@router.get("/flows/{flow_id}/export.json")
def export_json(flow: FlowDep, ctx: ExportCtx, db: DB) -> Response:
    return attachment(service.export_document(ctx, db, flow), "application/json", f"flow-{flow.id}.json")


@router.get("/flows/{flow_id}/export.mmd")
def export_mermaid(flow: FlowDep, ctx: ExportCtx, db: DB) -> Response:
    return attachment(service.export_mermaid(ctx, db, flow), "text/plain; charset=utf-8", f"flow-{flow.id}.mmd")


@router.get("/flows/{flow_id}/snapshots", response_model=list[SnapshotSummary])
def list_snapshots(flow: FlowDep, ctx: Ctx, db: DB) -> list[SnapshotSummary]:
    return [service.snapshot_summary(s) for s in service.list_snapshots(db, ctx, flow)]


@router.post("/flows/{flow_id}/snapshots", response_model=SnapshotSummary, status_code=201)
def create_snapshot(flow: FlowDep, body: SnapshotIn, ctx: WriteCtx, db: DB) -> SnapshotSummary:
    return service.snapshot_summary(service.create_snapshot(ctx, db, flow, body))


@router.get("/flows/{flow_id}/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(flow: FlowDep, snapshot_id: str, ctx: Ctx, db: DB) -> SnapshotOut:
    return service.snapshot_out(service.snapshot_of(db, ctx, flow, snapshot_id))


@router.post("/flows/{flow_id}/snapshots/{snapshot_id}/restore", response_model=FlowOut)
def restore_snapshot(flow: FlowDep, snapshot_id: str, ctx: WriteCtx, db: DB) -> FlowOut:
    snap = service.snapshot_of(db, ctx, flow, snapshot_id)
    return service.flow_out(service.restore_snapshot(ctx, db, flow, snap))
