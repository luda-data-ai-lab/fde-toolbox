from datetime import date
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

SESSION_TYPES = ("interview", "coaching")
SESSION_STATUSES = ("planned", "in_progress", "done")
ACTION_STATUSES = ("open", "in_progress", "done", "cancelled")


class CoachSubject(TenantScopedModel):
    """Interviewee (or mentee for coaching sessions) within an engagement."""

    __tablename__ = "coach_subjects"

    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    system_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoachCustomQuestion(TenantScopedModel):
    """Tenant-owned question, optionally cloned from a question bank asset."""

    __tablename__ = "coach_custom_questions"

    engagement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    audience: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    follow_ups: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class CoachSession(TenantScopedModel):
    __tablename__ = "coach_sessions"

    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="interview")
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("coach_subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    session_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoachSessionQuestion(TenantScopedModel):
    """A question on a session worksheet; text is snapshotted from the bank or custom question."""

    __tablename__ = "coach_session_questions"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coach_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    custom_question_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("coach_custom_questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    custom_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    follow_ups: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CoachInsight(TenantScopedModel):
    __tablename__ = "coach_insights"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coach_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_question_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("coach_session_questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class CoachActionItem(TenantScopedModel):
    __tablename__ = "coach_action_items"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coach_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insight_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("coach_insights.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
