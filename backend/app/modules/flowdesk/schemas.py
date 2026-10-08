from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import AssetRef, ORMModel

FlowKind = Literal["as_is", "to_be"]
Perspective = Literal["business", "pm", "developer", "executive", "consultant"]
NodeType = Literal["start", "end", "task", "decision", "system", "document", "role", "note"]

MAX_NODES = 500
MAX_EDGES = 1000
MAX_LANES = 30


class Position(BaseModel):
    x: float = 0
    y: float = 0


class GraphNode(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: NodeType = "task"
    label: str = Field(default="", max_length=300)
    lane: str | None = Field(default=None, max_length=100)
    system_id: str | None = Field(default=None, max_length=36)
    position: Position = Field(default_factory=Position)
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=200)


class FlowGraph(BaseModel):
    """Canvas graph JSON (`schema_version` 1); lanes are swimlane names, nodes reference them by name."""

    schema_version: Literal[1] = 1
    lanes: list[str] = Field(default_factory=list, max_length=MAX_LANES)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=MAX_NODES)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=MAX_EDGES)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if len(set(self.lanes)) != len(self.lanes) or any(not lane.strip() or len(lane) > 100 for lane in self.lanes):
            raise ValueError("lanes must be unique, non-empty names")
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate node id")
        if len({e.id for e in self.edges}) != len(self.edges):
            raise ValueError("duplicate edge id")
        known = set(ids)
        if any(e.source not in known or e.target not in known for e in self.edges):
            raise ValueError("edge references an unknown node")
        lanes = set(self.lanes)
        if any(n.lane is not None and n.lane not in lanes for n in self.nodes):
            raise ValueError("node references an unknown lane")
        return self


class FlowIn(BaseModel):
    engagement_id: str
    kind: FlowKind = "as_is"
    perspective: Perspective = "business"
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    template_ref: AssetRef | None = None
    graph: FlowGraph | None = None


class FlowPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    perspective: Perspective | None = None
    description: str | None = None
    graph: FlowGraph | None = None


class FlowSummary(ORMModel):
    tenant_id: str
    engagement_id: str
    kind: str
    pair_id: str | None
    perspective: str
    title: str
    description: str | None
    template_ref: AssetRef | None
    node_count: int = 0


class FlowOut(FlowSummary):
    graph: FlowGraph


class PairIn(BaseModel):
    """Link an existing opposite-kind flow (`flow_id`) or create a new counterpart."""

    flow_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    copy_graph: bool = True


class SnapshotIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class SnapshotSummary(ORMModel):
    flow_id: str
    version: int
    note: str | None
    node_count: int = 0


class SnapshotOut(SnapshotSummary):
    graph: FlowGraph


class TemplateOut(BaseModel):
    asset_id: str
    version: int
    asset_key: str
    title: str
    graph: FlowGraph


class FlowMeta(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: FlowKind = "as_is"
    perspective: Perspective = "business"
    description: str | None = None


class FlowDocument(BaseModel):
    """Re-importable JSON export of one flow."""

    schema_version: Literal[1] = 1
    kind: Literal["flowdesk_flow"] = "flowdesk_flow"
    flow: FlowMeta
    graph: FlowGraph


class ImportIn(BaseModel):
    engagement_id: str
    document: FlowDocument
