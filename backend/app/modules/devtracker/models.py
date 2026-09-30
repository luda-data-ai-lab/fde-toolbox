from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel, utcnow

PROJECT_STATUSES = ("planning", "active", "on_hold", "done")
TASK_STATUSES = ("todo", "in_progress", "review", "done", "on_hold")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")


class DevProject(TenantScopedModel):
    __tablename__ = "dev_projects"

    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    stack: Mapped[str | None] = mapped_column(String(300), nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    env_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deploy_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class DevTask(TenantScopedModel):
    __tablename__ = "dev_tasks"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dev_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="todo")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    assignee_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    due: Mapped[date | None] = mapped_column(Date, nullable=True)
    pause_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DevPrompt(TenantScopedModel):
    __tablename__ = "dev_prompts"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dev_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
