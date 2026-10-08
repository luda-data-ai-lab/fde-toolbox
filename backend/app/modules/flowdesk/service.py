import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.assets.models import AssetItem
from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.refs import ensure_tenant_refs
from app.core.schemas import AssetRef
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement
from app.db.base import Base
from app.modules.flowdesk.mermaid import to_mermaid
from app.modules.flowdesk.models import Flow, FlowSnapshot
from app.modules.flowdesk.schemas import (
    FlowDocument,
    FlowGraph,
    FlowIn,
    FlowMeta,
    FlowOut,
    FlowPatch,
    FlowSummary,
    GraphEdge,
    GraphNode,
    ImportIn,
    PairIn,
    Position,
    SnapshotIn,
    SnapshotOut,
    SnapshotSummary,
    TemplateOut,
)

TEMPLATE_TYPE = "flow_template"
LANE_HEIGHT = 140
COLUMN_WIDTH = 200
OPPOSITE = {"as_is": "to_be", "to_be": "as_is"}
_TEMPLATE_TYPES = {"start", "end", "task", "decision", "system", "document", "role", "note"}


def _flows(db: Session, ctx: TenantContext) -> TenantScopedRepository[Flow]:
    return TenantScopedRepository(db, ctx, Flow)


def _snapshots(db: Session, ctx: TenantContext) -> TenantScopedRepository[FlowSnapshot]:
    return TenantScopedRepository(db, ctx, FlowSnapshot)


def _node_count(graph: dict[str, Any]) -> int:
    nodes = graph.get("nodes")
    return len(nodes) if isinstance(nodes, list) else 0


def summary_out(flow: Flow) -> FlowSummary:
    return FlowSummary.model_validate(flow).model_copy(update={"node_count": _node_count(flow.graph)})


def flow_out(flow: Flow) -> FlowOut:
    return FlowOut.model_validate(flow).model_copy(update={"node_count": _node_count(flow.graph)})


def snapshot_summary(snap: FlowSnapshot) -> SnapshotSummary:
    return SnapshotSummary.model_validate(snap).model_copy(update={"node_count": _node_count(snap.graph)})


def snapshot_out(snap: FlowSnapshot) -> SnapshotOut:
    return SnapshotOut.model_validate(snap).model_copy(update={"node_count": _node_count(snap.graph)})


# --- templates ---------------------------------------------------------------


def template_graph(payload: dict[str, Any]) -> FlowGraph:
    """Lay out a LUDA flow template (lanes, nodes, from/to edges) on the canvas grid."""
    lanes = [str(x) for x in payload.get("lanes", [])]
    row = {name: i for i, name in enumerate(lanes)}
    nodes: list[GraphNode] = []
    for i, raw in enumerate(payload.get("nodes", [])):
        lane = raw.get("lane")
        node_type = raw.get("type") if raw.get("type") in _TEMPLATE_TYPES else "task"
        nodes.append(
            GraphNode(
                id=str(raw["id"]),
                type=node_type,
                label=str(raw.get("label", "")),
                lane=lane if lane in row else None,
                position=Position(x=40 + i * COLUMN_WIDTH, y=40 + row.get(lane, len(lanes)) * LANE_HEIGHT),
            )
        )
    edges = [
        GraphEdge(
            id=f"e{i}", source=str(raw.get("from", raw.get("source"))), target=str(raw.get("to", raw.get("target")))
        ).model_copy(update={"label": raw.get("label")})
        for i, raw in enumerate(payload.get("edges", []))
    ]
    return FlowGraph(lanes=lanes, nodes=nodes, edges=edges)


def _template(item: AssetItem) -> TemplateOut:
    try:
        graph = template_graph(item.payload)
    except (ValidationError, KeyError, TypeError) as exc:
        raise AppError(422, "invalid_flow_template") from exc
    return TemplateOut(
        asset_id=item.asset_id, version=item.version, asset_key=item.asset_key, title=item.title, graph=graph
    )


def list_templates(db: Session) -> list[TemplateOut]:
    rows = db.scalars(
        select(AssetItem)
        .where(AssetItem.asset_type == TEMPLATE_TYPE, AssetItem.status == "published")
        .order_by(AssetItem.title, AssetItem.version.desc())
    ).all()
    latest: dict[str, AssetItem] = {}
    for row in rows:
        latest.setdefault(row.asset_id, row)
    return [_template(item) for item in latest.values()]


def _resolve_template(db: Session, ref: AssetRef) -> FlowGraph:
    item = db.scalars(
        select(AssetItem).where(
            AssetItem.asset_type == TEMPLATE_TYPE, AssetItem.asset_id == ref.asset_id, AssetItem.version == ref.version
        )
    ).first()
    if item is None:
        raise AppError(422, "invalid_reference", detail={"field": "template_ref"})
    return _template(item).graph


# --- graph helpers -----------------------------------------------------------


def _system_ids(graph: FlowGraph) -> list[str]:
    return [n.system_id for n in graph.nodes if n.system_id]


def _check_systems(db: Session, ctx: TenantContext, graph: FlowGraph) -> None:
    ensure_tenant_refs(db, ctx, "systems", _system_ids(graph), "graph.nodes.system_id")


def system_names(db: Session, ctx: TenantContext, graph: FlowGraph) -> dict[str, str]:
    ids = set(_system_ids(graph))
    if not ids:
        return {}
    table = Base.metadata.tables["systems"]
    rows = db.execute(
        select(table.c.id, table.c.name).where(table.c.tenant_id == ctx.tenant_id, table.c.id.in_(ids))
    ).all()
    return {r.id: r.name for r in rows}


def _drop_missing_systems(db: Session, ctx: TenantContext, graph: FlowGraph) -> FlowGraph:
    """Unlink system references that don't exist in this tenant (imports, restored snapshots)."""
    known = system_names(db, ctx, graph)
    nodes = [
        n if n.system_id is None or n.system_id in known else n.model_copy(update={"system_id": None})
        for n in graph.nodes
    ]
    return graph.model_copy(update={"nodes": nodes})


def _dump(graph: FlowGraph) -> dict[str, Any]:
    return graph.model_dump(mode="json")


def _check_engagement(db: Session, ctx: TenantContext, engagement_id: str) -> None:
    TenantScopedRepository(db, ctx, Engagement).ensure_ref(engagement_id, "engagement_id")


# --- flows -------------------------------------------------------------------


@audited("flowdesk.flow_create", "flow")
def create_flow(ctx: TenantContext, db: Session, body: FlowIn) -> Flow:
    _check_engagement(db, ctx, body.engagement_id)
    graph = body.graph or (_resolve_template(db, body.template_ref) if body.template_ref else FlowGraph())
    _check_systems(db, ctx, graph)
    values = body.model_dump(exclude={"graph", "template_ref"})
    return _flows(db, ctx).create(
        **values,
        template_ref=body.template_ref.model_dump() if body.template_ref else None,
        graph=_dump(graph),
    )


@audited("flowdesk.flow_update", "flow")
def update_flow(ctx: TenantContext, db: Session, flow: Flow, body: FlowPatch) -> Flow:
    data = {
        k: v
        for k, v in body.model_dump(exclude_unset=True, exclude={"graph"}).items()
        if v is not None or k == "description"
    }
    if body.graph is not None:
        _check_systems(db, ctx, body.graph)
        data["graph"] = _dump(body.graph)
    return _flows(db, ctx).update(flow, **data)


def _counterpart(db: Session, ctx: TenantContext, flow: Flow) -> Flow | None:
    return _flows(db, ctx).get(flow.pair_id) if flow.pair_id else None


@audited("flowdesk.flow_delete", "flow")
def delete_flow(ctx: TenantContext, db: Session, flow: Flow) -> str:
    other = _counterpart(db, ctx, flow)
    if other is not None:
        other.pair_id = None
    _flows(db, ctx).delete(flow)
    return flow.id


@audited("flowdesk.flow_pair", "flow")
def pair_flow(ctx: TenantContext, db: Session, flow: Flow, body: PairIn) -> Flow:
    if flow.pair_id is not None:
        raise AppError(409, "flow_already_paired")
    repo = _flows(db, ctx)
    if body.flow_id is not None:
        other = repo.get(body.flow_id)
        if (
            other is None
            or other.id == flow.id
            or other.kind != OPPOSITE[flow.kind]
            or other.engagement_id != flow.engagement_id
            or other.pair_id is not None
        ):
            raise AppError(422, "invalid_pair", detail={"field": "flow_id"})
    else:
        kind = OPPOSITE[flow.kind]
        suffix = "To-Be" if kind == "to_be" else "As-Is"
        other = repo.create(
            engagement_id=flow.engagement_id,
            kind=kind,
            perspective=flow.perspective,
            title=body.title or f"{flow.title} ({suffix})",
            description=flow.description,
            template_ref=flow.template_ref,
            graph=json.loads(json.dumps(flow.graph)) if body.copy_graph else _dump(FlowGraph()),
        )
    flow.pair_id = other.id
    other.pair_id = flow.id
    db.flush()
    return other


@audited("flowdesk.flow_unpair", "flow")
def unpair_flow(ctx: TenantContext, db: Session, flow: Flow) -> Flow:
    other = _counterpart(db, ctx, flow)
    if other is not None:
        other.pair_id = None
    flow.pair_id = None
    db.flush()
    return flow


def pair_of(db: Session, ctx: TenantContext, flow: Flow) -> Flow:
    other = _counterpart(db, ctx, flow)
    if other is None:
        raise AppError(404, "not_found")
    return other


# --- snapshots ---------------------------------------------------------------


def list_snapshots(db: Session, ctx: TenantContext, flow: Flow) -> list[FlowSnapshot]:
    repo = _snapshots(db, ctx)
    return repo.all(repo.query().where(FlowSnapshot.flow_id == flow.id).order_by(FlowSnapshot.version.desc()))


def snapshot_of(db: Session, ctx: TenantContext, flow: Flow, snapshot_id: str) -> FlowSnapshot:
    snap = _snapshots(db, ctx).get_or_404(snapshot_id)
    if snap.flow_id != flow.id:
        raise AppError(404, "not_found")
    return snap


@audited("flowdesk.snapshot_create", "flow_snapshot")
def create_snapshot(ctx: TenantContext, db: Session, flow: Flow, body: SnapshotIn) -> FlowSnapshot:
    repo = _snapshots(db, ctx)
    latest = db.scalar(
        select(func.max(FlowSnapshot.version)).where(
            FlowSnapshot.tenant_id == ctx.tenant_id, FlowSnapshot.flow_id == flow.id
        )
    )
    return repo.create(
        flow_id=flow.id, version=(latest or 0) + 1, graph=json.loads(json.dumps(flow.graph)), note=body.note
    )


@audited("flowdesk.snapshot_restore", "flow")
def restore_snapshot(ctx: TenantContext, db: Session, flow: Flow, snap: FlowSnapshot) -> Flow:
    graph = _drop_missing_systems(db, ctx, FlowGraph.model_validate(snap.graph))
    return _flows(db, ctx).update(flow, graph=_dump(graph))


# --- import / export ---------------------------------------------------------


def _record_export(ctx: TenantContext, db: Session, flow: Flow, fmt: str) -> None:
    record(
        db,
        action="flowdesk.flow_export",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="flow",
        target_id=flow.id,
        detail={"format": fmt},
        ip=ctx.ip,
    )
    db.commit()


def export_document(ctx: TenantContext, db: Session, flow: Flow) -> str:
    doc = FlowDocument(
        flow=FlowMeta(title=flow.title, kind=flow.kind, perspective=flow.perspective, description=flow.description),
        graph=FlowGraph.model_validate(flow.graph),
    )
    _record_export(ctx, db, flow, "json")
    return json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, indent=2)


def export_mermaid(ctx: TenantContext, db: Session, flow: Flow) -> str:
    graph = FlowGraph.model_validate(flow.graph)
    text = to_mermaid(graph, system_names(db, ctx, graph))
    _record_export(ctx, db, flow, "mermaid")
    return text


@audited("flowdesk.flow_import", "flow")
def import_flow(ctx: TenantContext, db: Session, body: ImportIn) -> Flow:
    _check_engagement(db, ctx, body.engagement_id)
    meta = body.document.flow
    graph = _drop_missing_systems(db, ctx, body.document.graph)
    return _flows(db, ctx).create(
        engagement_id=body.engagement_id,
        kind=meta.kind,
        perspective=meta.perspective,
        title=meta.title,
        description=meta.description,
        graph=_dump(graph),
    )
