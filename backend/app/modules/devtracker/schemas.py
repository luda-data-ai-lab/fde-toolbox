from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

ProjectStatus = Literal["planning", "active", "on_hold", "done"]
TaskStatus = Literal["todo", "in_progress", "review", "done", "on_hold"]
TaskPriority = Literal["low", "medium", "high", "urgent"]
IssueKind = Literal["bug", "improvement", "question"]
IssueStatus = Literal["open", "in_progress", "resolved", "closed"]


class ProjectIn(BaseModel):
    engagement_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus = "planning"
    stack: str | None = Field(default=None, max_length=300)
    repo_url: str | None = Field(default=None, max_length=500)
    env_notes: str | None = None
    deploy_notes: str | None = None
    spec_document_ids: list[str] = Field(default_factory=list)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus | None = None
    stack: str | None = Field(default=None, max_length=300)
    repo_url: str | None = Field(default=None, max_length=500)
    env_notes: str | None = None
    deploy_notes: str | None = None
    spec_document_ids: list[str] | None = None


class ProjectOut(ORMModel):
    tenant_id: str
    engagement_id: str
    name: str
    description: str | None
    status: str
    stack: str | None
    repo_url: str | None
    env_notes: str | None
    deploy_notes: str | None
    spec_document_ids: list[str]


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    assignee_id: str | None = None
    due: date | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: str | None = None
    due: date | None = None
    pause_note: str | None = None
    resume_note: str | None = None


class PauseIn(BaseModel):
    pause_note: str = Field(min_length=1)
    resume_note: str | None = None


class TaskOut(ORMModel):
    tenant_id: str
    project_id: str
    title: str
    description: str | None
    status: str
    priority: str
    assignee_id: str | None
    due: date | None
    pause_note: str | None
    resume_note: str | None


class PromptIn(BaseModel):
    tool: str = Field(min_length=1, max_length=50)
    prompt: str = Field(min_length=1)
    result_summary: str | None = None
    at: datetime | None = None


class PromptPatch(BaseModel):
    tool: str | None = Field(default=None, min_length=1, max_length=50)
    prompt: str | None = Field(default=None, min_length=1)
    result_summary: str | None = None


class PromptOut(ORMModel):
    tenant_id: str
    task_id: str
    tool: str
    prompt: str
    result_summary: str | None
    at: datetime


class ProjectDashboard(BaseModel):
    project: ProjectOut
    status_counts: dict[str, int]
    total_tasks: int
    progress: float
    overdue_tasks: list[TaskOut]
    paused_tasks: list[TaskOut]
    recent_prompts: list[PromptOut]


class IssueSource(BaseModel):
    module: Literal["agenthub"]
    instance_id: str
    note: str | None = Field(default=None, max_length=2000)


class IssueIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: IssueKind = "bug"
    status: IssueStatus = "open"
    priority: TaskPriority = "medium"
    description: str | None = None
    source: IssueSource | None = None


class IssuePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    kind: IssueKind | None = None
    status: IssueStatus | None = None
    priority: TaskPriority | None = None
    description: str | None = None


class IssueOut(ORMModel):
    tenant_id: str
    project_id: str
    title: str
    kind: str
    status: str
    priority: str
    description: str | None
    source: dict[str, Any] | None
