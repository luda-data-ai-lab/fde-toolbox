from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.auth.deps import DB
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, WriteCtx, path_entity, repo
from app.modules.devtracker import service
from app.modules.devtracker.models import DevProject, DevPrompt, DevTask
from app.modules.devtracker.schemas import (
    PauseIn,
    ProjectDashboard,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    PromptIn,
    PromptOut,
    PromptPatch,
    TaskIn,
    TaskOut,
    TaskPatch,
    TaskStatus,
)

router = APIRouter(prefix="/t/{tenant_id}/devtracker", tags=["devtracker"])

ProjectDep = Annotated[DevProject, Depends(path_entity(DevProject, "project_id"))]
TaskDep = Annotated[DevTask, Depends(path_entity(DevTask, "task_id"))]
PromptDep = Annotated[DevPrompt, Depends(path_entity(DevPrompt, "prompt_id"))]


@router.get("/projects", response_model=Page[ProjectOut])
def list_projects(
    ctx: Ctx, db: DB, limit: int = 50, cursor: str | None = None, engagement_id: str | None = None
) -> Page[ProjectOut]:
    r = repo(db, ctx, DevProject)
    stmt = r.query()
    if engagement_id:
        stmt = stmt.where(DevProject.engagement_id == engagement_id)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[ProjectOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, ctx: WriteCtx, db: DB) -> ProjectOut:
    return ProjectOut.model_validate(service.create_project(ctx, db, body))


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(obj: ProjectDep) -> ProjectOut:
    return ProjectOut.model_validate(obj)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(obj: ProjectDep, body: ProjectPatch, ctx: WriteCtx, db: DB) -> ProjectOut:
    return ProjectOut.model_validate(service.update_project(ctx, db, obj, body))


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(obj: ProjectDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_project(ctx, db, obj)
    return Response(status_code=204)


@router.get("/projects/{project_id}/dashboard", response_model=ProjectDashboard)
def project_dashboard(obj: ProjectDep, ctx: Ctx, db: DB) -> ProjectDashboard:
    return service.dashboard(ctx, db, obj)


@router.get("/projects/{project_id}/tasks", response_model=Page[TaskOut])
def list_tasks(
    obj: ProjectDep, ctx: Ctx, db: DB, limit: int = 200, cursor: str | None = None, status: TaskStatus | None = None
) -> Page[TaskOut]:
    r = repo(db, ctx, DevTask)
    stmt = r.query().where(DevTask.project_id == obj.id)
    if status:
        stmt = stmt.where(DevTask.status == status)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[TaskOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(obj: ProjectDep, body: TaskIn, ctx: WriteCtx, db: DB) -> TaskOut:
    return TaskOut.model_validate(service.create_task(ctx, db, obj, body))


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(obj: TaskDep) -> TaskOut:
    return TaskOut.model_validate(obj)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(obj: TaskDep, body: TaskPatch, ctx: WriteCtx, db: DB) -> TaskOut:
    return TaskOut.model_validate(service.update_task(ctx, db, obj, body))


@router.post("/tasks/{task_id}/pause", response_model=TaskOut)
def pause_task(obj: TaskDep, body: PauseIn, ctx: WriteCtx, db: DB) -> TaskOut:
    return TaskOut.model_validate(service.pause_task(ctx, db, obj, body))


@router.post("/tasks/{task_id}/resume", response_model=TaskOut)
def resume_task(obj: TaskDep, ctx: WriteCtx, db: DB) -> TaskOut:
    return TaskOut.model_validate(service.resume_task(ctx, db, obj))


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(obj: TaskDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_task(ctx, db, obj)
    return Response(status_code=204)


@router.get("/tasks/{task_id}/prompts", response_model=Page[PromptOut])
def list_prompts(obj: TaskDep, ctx: Ctx, db: DB, limit: int = 50, cursor: str | None = None) -> Page[PromptOut]:
    r = repo(db, ctx, DevPrompt)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=r.query().where(DevPrompt.task_id == obj.id))
    return Page(items=[PromptOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/tasks/{task_id}/prompts", response_model=PromptOut, status_code=201)
def create_prompt(obj: TaskDep, body: PromptIn, ctx: WriteCtx, db: DB) -> PromptOut:
    return PromptOut.model_validate(service.create_prompt(ctx, db, obj, body))


@router.get("/prompts/{prompt_id}", response_model=PromptOut)
def get_prompt(obj: PromptDep) -> PromptOut:
    return PromptOut.model_validate(obj)


@router.patch("/prompts/{prompt_id}", response_model=PromptOut)
def update_prompt(obj: PromptDep, body: PromptPatch, ctx: WriteCtx, db: DB) -> PromptOut:
    return PromptOut.model_validate(service.update_prompt(ctx, db, obj, body))


@router.delete("/prompts/{prompt_id}", status_code=204)
def delete_prompt(obj: PromptDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_prompt(ctx, db, obj)
    return Response(status_code=204)
