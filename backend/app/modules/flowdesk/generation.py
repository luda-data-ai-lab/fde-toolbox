"""FlowDesk generation: perspective-aware prompt builder and result parser.

The same prompt is sent through the LLM adapter or shown in prompt-copy mode, and both answers go
through `parse_json_result` + `to_graph`, so the two paths produce identical flows.
"""

from collections import deque

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterDisabled
from app.adapters.registry import LLM, get_adapter
from app.core.errors import AppError
from app.core.prompting import ResultParseError, build_json_prompt, parse_json_result
from app.core.systems.models import System
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.db.base import Base
from app.modules.flowdesk.schemas import (
    MAX_EDGES,
    MAX_LANES,
    MAX_NODES,
    FlowGraph,
    GenerateIn,
    GraphEdge,
    GraphNode,
    InsightOption,
    Position,
)

NODE_TYPES = ("start", "end", "task", "decision", "system", "document", "role", "note")
LANE_HEIGHT = 140
COLUMN_WIDTH = 200
MAX_INSIGHT_CHARS = 500
FEATURE = "flowdesk.generate"

PERSPECTIVES = {
    "business": (
        "Business user: describe the work exactly as staff perform it - who does each step, which documents "
        "and spreadsheets are used, manual hand-offs and waiting points. About 12-25 steps."
    ),
    "pm": (
        "Project manager: emphasise owners, deliverables, approvals and decision points, and mark bottlenecks "
        "that affect schedule. About 10-20 steps."
    ),
    "developer": (
        "Developer: emphasise which system runs each step, data passed between systems, interface points and "
        "exception branches. Use `system` nodes for automated steps. About 15-30 steps."
    ),
    "executive": (
        "Executive: summarise only the key stages and decisions with business impact. Keep it to 5-10 steps."
    ),
    "consultant": (
        "Consultant: show the process and add `note` nodes that point out problems (As-Is) or the improvement "
        "each change brings (To-Be). About 10-20 steps."
    ),
}

KIND = {
    "as_is": "the current (As-Is) process as it runs today",
    "to_be": "the improved (To-Be) process, removing the problems and manual work described in the inputs",
}
LANGUAGE = {"ko": "Korean", "en": "English"}


class GeneratedNode(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: str = Field(default="task", description="One of: " + ", ".join(NODE_TYPES))
    label: str = Field(default="", max_length=300)
    lane: str | None = Field(default=None, max_length=100, description="Name of one of `lanes`")
    system: str | None = Field(default=None, max_length=200, description="Registered system name, if any")


class GeneratedEdge(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=200, description="Condition for decision branches")


class GeneratedFlow(BaseModel):
    lanes: list[str] = Field(default_factory=list, max_length=MAX_LANES, description="Departments or roles")
    nodes: list[GeneratedNode] = Field(min_length=1, max_length=MAX_NODES)
    edges: list[GeneratedEdge] = Field(default_factory=list, max_length=MAX_EDGES)


# --- inputs ------------------------------------------------------------------


def _insight_rows(
    db: Session, ctx: TenantContext, engagement_id: str | None, ids: list[str] | None = None
) -> list[InsightOption]:
    """DiscoveryQ insights of the engagement, read by table name (modules must not import each other)."""
    tables = Base.metadata.tables
    ins, ses = tables["discovery_insights"], tables["discovery_sessions"]
    stmt = (
        select(ins.c.id, ins.c.text, ins.c.tags, ses.c.id.label("session_id"), ses.c.title)
        .join(ses, ses.c.id == ins.c.session_id)
        .where(ins.c.tenant_id == ctx.tenant_id, ses.c.tenant_id == ctx.tenant_id)
        .order_by(ses.c.created_at, ins.c.created_at)
    )
    if engagement_id:
        stmt = stmt.where(ses.c.engagement_id == engagement_id)
    if ids is not None:
        stmt = stmt.where(ins.c.id.in_(ids))
    return [
        InsightOption(id=r.id, text=r.text, tags=list(r.tags or []), session_id=r.session_id, session_title=r.title)
        for r in db.execute(stmt).all()
    ]


def list_insights(db: Session, ctx: TenantContext, engagement_id: str | None) -> list[InsightOption]:
    return _insight_rows(db, ctx, engagement_id)


def registered_systems(db: Session, ctx: TenantContext) -> list[System]:
    repo = TenantScopedRepository(db, ctx, System)
    return list(db.scalars(repo.query().order_by(System.name)).all())


def selected_insights(db: Session, ctx: TenantContext, body: GenerateIn) -> list[InsightOption]:
    ids = list(dict.fromkeys(body.insight_ids))
    if not ids:
        return []
    rows = _insight_rows(db, ctx, body.engagement_id, ids)
    if len(rows) != len(ids):
        raise AppError(422, "invalid_reference", detail={"field": "insight_ids"})
    return rows


# --- prompt ------------------------------------------------------------------


def build_prompt(body: GenerateIn, insights: list[InsightOption], systems: list[System]) -> str:
    """The task prompt without the JSON instruction (the LLM client and copy mode append it)."""
    parts = [
        "You are a business process analyst. Draw a swimlane business process flow.",
        f'Flow title: "{body.title}". Draw {KIND[body.kind]}.',
        f"Audience perspective - {PERSPECTIVES[body.perspective]}",
    ]
    if body.description.strip():
        parts.append(f"Process description from the FDE:\n{body.description.strip()}")
    if insights:
        lines = "\n".join(f"- [{i.session_title}] {i.text.strip()[:MAX_INSIGHT_CHARS]}" for i in insights)
        parts.append(f"Interview insights (DiscoveryQ):\n{lines}")
    if systems:
        lines = "\n".join(f"- {s.name}" + (f" ({s.short_name})" if s.short_name else "") for s in systems)
        parts.append(
            "Registered systems. When a step runs in one of them, put its exact name in the node's `system`:\n" + lines
        )
    parts.append(
        "\n".join(
            [
                "Rules:",
                "- `lanes` are the departments or roles that perform the work; every node except notes has a lane.",
                "- Node types: start, end, task (work step), decision (branch), system (automated step in a system),"
                " document (form/report/spreadsheet), role (external party), note (remark, not connected).",
                "- Exactly one start node and at least one end node; every connected node is reachable from start.",
                "- Each decision has two or more outgoing edges with a short `label` (the condition).",
                "- Node ids are short and unique (n1, n2, ...); edges reference node ids.",
                f"- Write lane names and labels in {LANGUAGE[body.lang]}, at most about 30 characters each.",
            ]
        )
    )
    return "\n\n".join(parts)


def copy_prompt(body: GenerateIn, insights: list[InsightOption], systems: list[System]) -> str:
    return build_json_prompt(build_prompt(body, insights, systems), GeneratedFlow)


def llm_available(ctx: TenantContext, db: Session) -> bool:
    try:
        get_adapter(ctx, db, LLM.key)
    except AdapterDisabled:
        return False
    return True


# --- result ------------------------------------------------------------------


def _columns(ids: list[str], edges: list[GraphEdge]) -> dict[str, int]:
    """Breadth-first depth from the roots; unreachable nodes continue after the deepest column."""
    incoming = {e.target for e in edges if e.source != e.target}
    out: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        out[e.source].append(e.target)
    roots = [i for i in ids if i not in incoming] or ids[:1]
    depth: dict[str, int] = dict.fromkeys(roots, 0)
    queue = deque(roots)
    while queue:
        cur = queue.popleft()
        for nxt in out[cur]:
            if nxt not in depth:
                depth[nxt] = depth[cur] + 1
                queue.append(nxt)
    tail = max(depth.values(), default=-1) + 1
    for i in ids:
        if i not in depth:
            depth[i] = tail
            tail += 1
    return depth


def to_graph(result: GeneratedFlow, systems: list[System]) -> FlowGraph:
    """Normalise a generated flow into a valid canvas graph and lay it out on the lane grid."""
    by_name: dict[str, System] = {}
    for s in systems:
        by_name.setdefault(s.name.strip().lower(), s)
        if s.short_name:
            by_name.setdefault(s.short_name.strip().lower(), s)

    lanes: list[str] = []

    def lane_of(name: str | None) -> str | None:
        name = (name or "").strip()[:100]
        if not name:
            return None
        if name not in lanes and len(lanes) < MAX_LANES:
            lanes.append(name)
        return name if name in lanes else None

    for lane in result.lanes:
        lane_of(lane)

    nodes: list[GraphNode] = []
    seen: set[str] = set()
    for raw in result.nodes:
        if raw.id in seen:
            continue
        seen.add(raw.id)
        node_type = raw.type.strip().lower() if raw.type.strip().lower() in NODE_TYPES else "task"
        system = by_name.get((raw.system or "").strip().lower())
        label = raw.label.strip() or (system.name if system else (raw.system or "").strip())[:300]
        nodes.append(
            GraphNode(
                id=raw.id,
                type=node_type,
                label=label,
                lane=lane_of(raw.lane),
                system_id=system.id if system else None,
            )
        )
    edges = [
        GraphEdge(id=f"e{i + 1}", source=e.source, target=e.target, label=(e.label or "").strip() or None)
        for i, e in enumerate(x for x in result.edges if x.source in seen and x.target in seen)
    ]
    columns = _columns([n.id for n in nodes], edges)
    row = {name: i for i, name in enumerate(lanes)}
    used: set[tuple[int, int]] = set()
    placed: list[GraphNode] = []
    for n in sorted(nodes, key=lambda n: columns[n.id]):
        r = row.get(n.lane, len(lanes)) if n.lane else len(lanes)
        col = columns[n.id]
        while (col, r) in used:
            col += 1
        used.add((col, r))
        placed.append(n.model_copy(update={"position": Position(x=40 + col * COLUMN_WIDTH, y=40 + r * LANE_HEIGHT)}))
    order = {n.id: i for i, n in enumerate(nodes)}
    placed.sort(key=lambda n: order[n.id])
    return FlowGraph(lanes=lanes, nodes=placed, edges=edges)


def parse_answer(text: str) -> GeneratedFlow:
    try:
        return parse_json_result(text, GeneratedFlow)
    except ResultParseError as exc:
        raise AppError(422, "flow_result_invalid", detail={"reason": exc.reason, "errors": exc.errors[:20]}) from exc
