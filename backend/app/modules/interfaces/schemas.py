from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

LinkType = Literal["db_link", "api", "file", "mq", "eai", "other"]
InterfaceStatus = Literal["planned", "developing", "operating", "retired"]


class InterfaceIn(BaseModel):
    if_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    source_system_id: str
    target_system_id: str
    link_type: LinkType = "other"
    schedule: str | None = Field(default=None, max_length=100)
    description: str | None = None
    daily_volume: int | None = Field(default=None, ge=0)
    owner: str | None = Field(default=None, max_length=100)
    status: InterfaceStatus = "operating"
    notes: str | None = None


class InterfacePatch(BaseModel):
    if_code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=300)
    source_system_id: str | None = None
    target_system_id: str | None = None
    link_type: LinkType | None = None
    schedule: str | None = Field(default=None, max_length=100)
    description: str | None = None
    daily_volume: int | None = Field(default=None, ge=0)
    owner: str | None = Field(default=None, max_length=100)
    status: InterfaceStatus | None = None
    notes: str | None = None


class InterfaceOut(ORMModel):
    tenant_id: str
    if_code: str
    name: str
    source_system_id: str
    target_system_id: str
    link_type: str
    schedule: str | None
    description: str | None
    daily_volume: int | None
    owner: str | None
    status: str
    notes: str | None


class UploadOut(ORMModel):
    tenant_id: str
    file_id: str
    status: str
    result: dict[str, Any]


class ApplyIn(BaseModel):
    register_systems: list[str] = Field(default_factory=list)


class SystemCount(BaseModel):
    system_id: str
    name: str
    outgoing: int
    incoming: int


class InterfaceDashboard(BaseModel):
    total: int
    by_link_type: dict[str, int]
    by_status: dict[str, int]
    by_system: list[SystemCount]


class GraphNode(BaseModel):
    id: str
    name: str
    short_name: str | None
    type: str
    degree: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    if_code: str
    name: str
    link_type: str
    status: str


class InterfaceGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
