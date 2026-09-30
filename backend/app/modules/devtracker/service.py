from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit.service import audited
from app.core.errors import AppError
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement
from app.core.users.service import user_has_tenant
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
)


def _check_assignee(db: Session, ctx: TenantContext, assignee_id: str | None) -> None:
    if assignee_id is not None and not user_has_tenant(db, assignee_id, ctx.tenant_id):
        raise AppError(422, "invalid_reference", detail={"field": "assignee_id"})


@audited("devtracker.project_create", "dev_project")
def create_project(ctx: TenantContext, db: Session, body: ProjectIn) -> DevProject:
    TenantScopedRepository(db, ctx, Engagement).ensure_ref(body.engagement_id, "engagement_id")
    return TenantScopedRepository(db, ctx, DevProject).create(**body.model_dump())


@audited("devtracker.project_update", "dev_project")
def update_project(ctx: TenantContext, db: Session, obj: DevProject, body: ProjectPatch) -> DevProject:
    return TenantScopedRepository(db, ctx, DevProject).update(obj, **body.model_dump(exclude_unset=True))


@audited("devtracker.project_delete", "dev_project")
def delete_project(ctx: TenantContext, db: Session, obj: DevProject) -> str:
    TenantScopedRepository(db, ctx, DevProject).delete(obj)
    return obj.id


@audited("devtracker.task_create", "dev_task")
def create_task(ctx: TenantContext, db: Session, project: DevProject, body: TaskIn) -> DevTask:
    _check_assignee(db, ctx, body.assignee_id)
    return TenantScopedRepository(db, ctx, DevTask).create(project_id=project.id, **body.model_dump())


@audited("devtracker.task_update", "dev_task")
def update_task(ctx: TenantContext, db: Session, obj: DevTask, body: TaskPatch) -> DevTask:
    data = body.model_dump(exclude_unset=True)
    _check_assignee(db, ctx, data.get("assignee_id"))
    return TenantScopedRepository(db, ctx, DevTask).update(obj, **data)


@audited("devtracker.task_pause", "dev_task")
def pause_task(ctx: TenantContext, db: Session, obj: DevTask, body: PauseIn) -> DevTask:
    return TenantScopedRepository(db, ctx, DevTask).update(
        obj, status="on_hold", pause_note=body.pause_note, resume_note=body.resume_note
    )


@audited("devtracker.task_resume", "dev_task")
def resume_task(ctx: TenantContext, db: Session, obj: DevTask) -> DevTask:
    return TenantScopedRepository(db, ctx, DevTask).update(obj, status="in_progress")


@audited("devtracker.task_delete", "dev_task")
def delete_task(ctx: TenantContext, db: Session, obj: DevTask) -> str:
    TenantScopedRepository(db, ctx, DevTask).delete(obj)
    return obj.id


@audited("devtracker.prompt_create", "dev_prompt")
def create_prompt(ctx: TenantContext, db: Session, task: DevTask, body: PromptIn) -> DevPrompt:
    values: dict[str, Any] = body.model_dump(exclude_none=True)
    return TenantScopedRepository(db, ctx, DevPrompt).create(task_id=task.id, **values)


@audited("devtracker.prompt_update", "dev_prompt")
def update_prompt(ctx: TenantContext, db: Session, obj: DevPrompt, body: PromptPatch) -> DevPrompt:
    return TenantScopedRepository(db, ctx, DevPrompt).update(obj, **body.model_dump(exclude_unset=True))


@audited("devtracker.prompt_delete", "dev_prompt")
def delete_prompt(ctx: TenantContext, db: Session, obj: DevPrompt) -> str:
    TenantScopedRepository(db, ctx, DevPrompt).delete(obj)
    return obj.id


def dashboard(ctx: TenantContext, db: Session, project: DevProject) -> ProjectDashboard:
    tasks = TenantScopedRepository(db, ctx, DevTask)
    counts: dict[str, int] = {
        str(k): int(v)
        for k, v in db.execute(
            select(DevTask.status, func.count())
            .where(DevTask.tenant_id == ctx.tenant_id, DevTask.project_id == project.id)
            .group_by(DevTask.status)
        )
    }
    total = sum(counts.values())
    base = tasks.query().where(DevTask.project_id == project.id)
    overdue = tasks.all(
        base.where(DevTask.due < date.today(), DevTask.status != "done").order_by(DevTask.due).limit(20)
    )
    paused = tasks.all(base.where(DevTask.status == "on_hold").order_by(DevTask.updated_at.desc()).limit(20))
    prompts = TenantScopedRepository(db, ctx, DevPrompt).all(
        select(DevPrompt)
        .join(DevTask, DevTask.id == DevPrompt.task_id)
        .where(DevPrompt.tenant_id == ctx.tenant_id, DevTask.project_id == project.id)
        .order_by(DevPrompt.at.desc())
        .limit(10)
    )
    return ProjectDashboard(
        project=ProjectOut.model_validate(project),
        status_counts=counts,
        total_tasks=total,
        progress=round(counts.get("done", 0) / total, 4) if total else 0.0,
        overdue_tasks=[TaskOut.model_validate(t) for t in overdue],
        paused_tasks=[TaskOut.model_validate(t) for t in paused],
        recent_prompts=[PromptOut.model_validate(p) for p in prompts],
    )


def home_summary(ctx: TenantContext, db: Session) -> dict[str, Any]:
    tasks = TenantScopedRepository(db, ctx, DevTask)
    open_count = (
        db.scalar(
            select(func.count())
            .select_from(DevTask)
            .where(DevTask.tenant_id == ctx.tenant_id, DevTask.status != "done")
        )
        or 0
    )
    paused = tasks.all(tasks.query().where(DevTask.status == "on_hold").order_by(DevTask.updated_at.desc()).limit(5))
    recent = tasks.all(tasks.query().order_by(DevTask.updated_at.desc()).limit(5))
    return {
        "open_tasks": open_count,
        "paused_tasks": [TaskOut.model_validate(t).model_dump(mode="json") for t in paused],
        "recent_tasks": [TaskOut.model_validate(t).model_dump(mode="json") for t in recent],
    }
