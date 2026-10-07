from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.assets.models import AssetItem
from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.exports import csv_text
from app.core.refs import ensure_tenant_refs
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement
from app.modules.discoveryq.models import (
    DiscoveryActionItem,
    DiscoveryCustomQuestion,
    DiscoveryInsight,
    DiscoverySession,
    DiscoverySessionQuestion,
    DiscoverySubject,
)
from app.modules.discoveryq.schemas import (
    ActionItemIn,
    ActionItemOut,
    ActionItemPatch,
    BankQuestion,
    BankSummary,
    CustomQuestionIn,
    CustomQuestionPatch,
    InsightIn,
    InsightOut,
    InsightPatch,
    QuestionBank,
    QuestionBankOut,
    QuestionBankPayload,
    QuestionRef,
    SessionIn,
    SessionOut,
    SessionPatch,
    SessionQuestionIn,
    SessionQuestionOut,
    SessionQuestionPatch,
    SubjectIn,
    SubjectOut,
    SubjectPatch,
    Worksheet,
)

BANK_TYPE = "question_bank"
Lang = Literal["ko", "en"]


def _invalid(field: str) -> AppError:
    return AppError(422, "invalid_reference", detail={"field": field})


# --- question bank -----------------------------------------------------------


def _bank_from(item: AssetItem) -> QuestionBank:
    try:
        payload = QuestionBankPayload.model_validate(item.payload)
    except ValidationError as exc:
        raise AppError(422, "invalid_question_bank") from exc
    return QuestionBank(asset_id=item.asset_id, version=item.version, title=item.title, **payload.model_dump())


def _published_banks(db: Session) -> list[AssetItem]:
    rows = db.scalars(
        select(AssetItem)
        .where(AssetItem.asset_type == BANK_TYPE, AssetItem.status == "published")
        .order_by(AssetItem.title, AssetItem.version.desc())
    ).all()
    latest: dict[str, AssetItem] = {}
    for row in rows:
        latest.setdefault(row.asset_id, row)
    return list(latest.values())


def question_bank(db: Session, asset_id: str | None, version: int | None) -> QuestionBankOut:
    banks = _published_banks(db)
    summaries = [BankSummary(asset_id=b.asset_id, version=b.version, title=b.title) for b in banks]
    item: AssetItem | None
    if asset_id is None:
        item = banks[0] if banks else None
    else:
        stmt = select(AssetItem).where(AssetItem.asset_type == BANK_TYPE, AssetItem.asset_id == asset_id)
        stmt = stmt.where(AssetItem.version == version) if version is not None else stmt
        item = db.scalars(stmt.order_by(AssetItem.version.desc())).first()
        if item is None:
            raise AppError(404, "not_found")
    return QuestionBankOut(bank=_bank_from(item) if item else None, banks=summaries)


def _resolve_ref(db: Session, ref: QuestionRef, field: str) -> tuple[str, BankQuestion]:
    item = db.scalars(
        select(AssetItem).where(
            AssetItem.asset_type == BANK_TYPE, AssetItem.asset_id == ref.asset_id, AssetItem.version == ref.version
        )
    ).first()
    if item is None:
        raise _invalid(field)
    for category in _bank_from(item).categories:
        for q in category.questions:
            if q.id == ref.question_id:
                return category.key, q
    raise _invalid(field)


# --- subjects ----------------------------------------------------------------


def _check_engagement(db: Session, ctx: TenantContext, engagement_id: str | None) -> None:
    TenantScopedRepository(db, ctx, Engagement).ensure_ref(engagement_id, "engagement_id")


@audited("discoveryq.subject_create", "discovery_subject")
def create_subject(ctx: TenantContext, db: Session, body: SubjectIn) -> DiscoverySubject:
    _check_engagement(db, ctx, body.engagement_id)
    ensure_tenant_refs(db, ctx, "systems", body.system_ids, "system_ids")
    return TenantScopedRepository(db, ctx, DiscoverySubject).create(**body.model_dump())


@audited("discoveryq.subject_update", "discovery_subject")
def update_subject(ctx: TenantContext, db: Session, obj: DiscoverySubject, body: SubjectPatch) -> DiscoverySubject:
    data = body.model_dump(exclude_unset=True)
    if data.get("system_ids") is not None:
        ensure_tenant_refs(db, ctx, "systems", data["system_ids"], "system_ids")
    elif "system_ids" in data:
        data["system_ids"] = []
    return TenantScopedRepository(db, ctx, DiscoverySubject).update(obj, **data)


@audited("discoveryq.subject_delete", "discovery_subject")
def delete_subject(ctx: TenantContext, db: Session, obj: DiscoverySubject) -> str:
    TenantScopedRepository(db, ctx, DiscoverySubject).delete(obj)
    return obj.id


# --- custom questions --------------------------------------------------------


@audited("discoveryq.custom_question_create", "discovery_custom_question")
def create_custom_question(ctx: TenantContext, db: Session, body: CustomQuestionIn) -> DiscoveryCustomQuestion:
    _check_engagement(db, ctx, body.engagement_id)
    values: dict[str, Any] = body.model_dump(exclude={"source_ref"})
    if body.source_ref is not None:
        category, q = _resolve_ref(db, body.source_ref, "source_ref")
        values["source_ref"] = body.source_ref.model_dump()
        values["category"] = body.category or category
        values["text"] = body.text or q.text
        values["tags"] = body.tags or q.tags
        values["audience"] = body.audience or q.audience
        values["follow_ups"] = q.follow_ups if body.follow_ups is None else body.follow_ups
    values["follow_ups"] = values.get("follow_ups") or []
    return TenantScopedRepository(db, ctx, DiscoveryCustomQuestion).create(**values)


@audited("discoveryq.custom_question_update", "discovery_custom_question")
def update_custom_question(
    ctx: TenantContext, db: Session, obj: DiscoveryCustomQuestion, body: CustomQuestionPatch
) -> DiscoveryCustomQuestion:
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k == "category"}
    return TenantScopedRepository(db, ctx, DiscoveryCustomQuestion).update(obj, **data)


@audited("discoveryq.custom_question_delete", "discovery_custom_question")
def delete_custom_question(ctx: TenantContext, db: Session, obj: DiscoveryCustomQuestion) -> str:
    TenantScopedRepository(db, ctx, DiscoveryCustomQuestion).delete(obj)
    return obj.id


# --- sessions ----------------------------------------------------------------


def _check_subject(db: Session, ctx: TenantContext, engagement_id: str, subject_id: str | None) -> None:
    if subject_id is None:
        return
    subject = TenantScopedRepository(db, ctx, DiscoverySubject).get(subject_id)
    if subject is None or subject.engagement_id != engagement_id:
        raise _invalid("subject_id")


@audited("discoveryq.session_create", "discovery_session")
def create_session(ctx: TenantContext, db: Session, body: SessionIn) -> DiscoverySession:
    _check_engagement(db, ctx, body.engagement_id)
    _check_subject(db, ctx, body.engagement_id, body.subject_id)
    return TenantScopedRepository(db, ctx, DiscoverySession).create(**body.model_dump())


@audited("discoveryq.session_update", "discovery_session")
def update_session(ctx: TenantContext, db: Session, obj: DiscoverySession, body: SessionPatch) -> DiscoverySession:
    data = body.model_dump(exclude_unset=True)
    for key in ("type", "title", "status"):
        if key in data and data[key] is None:
            del data[key]
    if "subject_id" in data:
        _check_subject(db, ctx, obj.engagement_id, data["subject_id"])
    return TenantScopedRepository(db, ctx, DiscoverySession).update(obj, **data)


@audited("discoveryq.session_delete", "discovery_session")
def delete_session(ctx: TenantContext, db: Session, obj: DiscoverySession) -> str:
    TenantScopedRepository(db, ctx, DiscoverySession).delete(obj)
    return obj.id


def session_filter(
    ctx: TenantContext,
    db: Session,
    *,
    engagement_id: str | None,
    type: str | None,
    subject_id: str | None,
    q: str | None,
) -> Select[DiscoverySession]:
    stmt = TenantScopedRepository(db, ctx, DiscoverySession).query()
    if engagement_id:
        stmt = stmt.where(DiscoverySession.engagement_id == engagement_id)
    if type:
        stmt = stmt.where(DiscoverySession.type == type)
    if subject_id:
        stmt = stmt.where(DiscoverySession.subject_id == subject_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(DiscoverySession.title.ilike(like), DiscoverySession.summary.ilike(like)))
    return stmt


# --- worksheet: questions, insights, action items ----------------------------


@audited("discoveryq.question_add", "discovery_session_question")
def add_question(
    ctx: TenantContext, db: Session, session: DiscoverySession, body: SessionQuestionIn
) -> DiscoverySessionQuestion:
    repo = TenantScopedRepository(db, ctx, DiscoverySessionQuestion)
    values: dict[str, Any] = {"session_id": session.id, "answer": body.answer}
    if body.question_ref is not None:
        category, q = _resolve_ref(db, body.question_ref, "question_ref")
        values |= {
            "question_ref": body.question_ref.model_dump(),
            "text": q.text,
            "category": category,
            "follow_ups": q.follow_ups,
        }
    elif body.custom_question_id is not None:
        custom = TenantScopedRepository(db, ctx, DiscoveryCustomQuestion).get(body.custom_question_id)
        if custom is None:
            raise _invalid("custom_question_id")
        values |= {
            "custom_question_id": custom.id,
            "text": custom.text,
            "category": custom.category,
            "follow_ups": list(custom.follow_ups),
        }
    else:
        values |= {"custom_text": body.custom_text, "text": body.custom_text, "follow_ups": []}
    last = db.scalar(
        select(func.max(DiscoverySessionQuestion.position)).where(
            DiscoverySessionQuestion.tenant_id == ctx.tenant_id, DiscoverySessionQuestion.session_id == session.id
        )
    )
    values["position"] = 0 if last is None else last + 1
    return repo.create(**values)


@audited("discoveryq.question_update", "discovery_session_question")
def update_question(
    ctx: TenantContext, db: Session, obj: DiscoverySessionQuestion, body: SessionQuestionPatch
) -> DiscoverySessionQuestion:
    data = body.model_dump(exclude_unset=True)
    if data.get("position", 0) is None:
        del data["position"]
    return TenantScopedRepository(db, ctx, DiscoverySessionQuestion).update(obj, **data)


@audited("discoveryq.question_delete", "discovery_session_question")
def delete_question(ctx: TenantContext, db: Session, obj: DiscoverySessionQuestion) -> str:
    TenantScopedRepository(db, ctx, DiscoverySessionQuestion).delete(obj)
    return obj.id


def _check_question(db: Session, ctx: TenantContext, session_id: str, question_id: str | None) -> None:
    if question_id is None:
        return
    q = TenantScopedRepository(db, ctx, DiscoverySessionQuestion).get(question_id)
    if q is None or q.session_id != session_id:
        raise _invalid("session_question_id")


def _clean_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for tag in (t.strip() for t in tags):
        if tag and tag not in seen:
            seen.append(tag[:50])
    return seen


@audited("discoveryq.insight_create", "discovery_insight")
def create_insight(ctx: TenantContext, db: Session, session: DiscoverySession, body: InsightIn) -> DiscoveryInsight:
    _check_question(db, ctx, session.id, body.session_question_id)
    values = body.model_dump()
    values["tags"] = _clean_tags(body.tags)
    return TenantScopedRepository(db, ctx, DiscoveryInsight).create(session_id=session.id, **values)


@audited("discoveryq.insight_update", "discovery_insight")
def update_insight(ctx: TenantContext, db: Session, obj: DiscoveryInsight, body: InsightPatch) -> DiscoveryInsight:
    data = body.model_dump(exclude_unset=True)
    if "session_question_id" in data:
        _check_question(db, ctx, obj.session_id, data["session_question_id"])
    if "tags" in data:
        data["tags"] = _clean_tags(data["tags"] or [])
    if "text" in data and data["text"] is None:
        del data["text"]
    return TenantScopedRepository(db, ctx, DiscoveryInsight).update(obj, **data)


@audited("discoveryq.insight_delete", "discovery_insight")
def delete_insight(ctx: TenantContext, db: Session, obj: DiscoveryInsight) -> str:
    TenantScopedRepository(db, ctx, DiscoveryInsight).delete(obj)
    return obj.id


def _check_insight(db: Session, ctx: TenantContext, session_id: str, insight_id: str | None) -> None:
    if insight_id is None:
        return
    insight = TenantScopedRepository(db, ctx, DiscoveryInsight).get(insight_id)
    if insight is None or insight.session_id != session_id:
        raise _invalid("insight_id")


@audited("discoveryq.action_item_create", "discovery_action_item")
def create_action_item(
    ctx: TenantContext, db: Session, session: DiscoverySession, body: ActionItemIn
) -> DiscoveryActionItem:
    _check_insight(db, ctx, session.id, body.insight_id)
    return TenantScopedRepository(db, ctx, DiscoveryActionItem).create(session_id=session.id, **body.model_dump())


@audited("discoveryq.action_item_update", "discovery_action_item")
def update_action_item(
    ctx: TenantContext, db: Session, obj: DiscoveryActionItem, body: ActionItemPatch
) -> DiscoveryActionItem:
    data = body.model_dump(exclude_unset=True)
    if "insight_id" in data:
        _check_insight(db, ctx, obj.session_id, data["insight_id"])
    for key in ("title", "status"):
        if key in data and data[key] is None:
            del data[key]
    return TenantScopedRepository(db, ctx, DiscoveryActionItem).update(obj, **data)


@audited("discoveryq.action_item_delete", "discovery_action_item")
def delete_action_item(ctx: TenantContext, db: Session, obj: DiscoveryActionItem) -> str:
    TenantScopedRepository(db, ctx, DiscoveryActionItem).delete(obj)
    return obj.id


def action_item_filter(
    ctx: TenantContext,
    db: Session,
    *,
    engagement_id: str | None,
    session_id: str | None,
    status: str | None,
) -> Select[DiscoveryActionItem]:
    stmt = TenantScopedRepository(db, ctx, DiscoveryActionItem).query()
    if engagement_id:
        stmt = stmt.join(DiscoverySession, DiscoverySession.id == DiscoveryActionItem.session_id).where(
            DiscoverySession.tenant_id == ctx.tenant_id, DiscoverySession.engagement_id == engagement_id
        )
    if session_id:
        stmt = stmt.where(DiscoveryActionItem.session_id == session_id)
    if status:
        stmt = stmt.where(DiscoveryActionItem.status == status)
    return stmt


def worksheet(ctx: TenantContext, db: Session, session: DiscoverySession) -> Worksheet:
    subject = TenantScopedRepository(db, ctx, DiscoverySubject).get(session.subject_id) if session.subject_id else None
    questions = TenantScopedRepository(db, ctx, DiscoverySessionQuestion)
    insights = TenantScopedRepository(db, ctx, DiscoveryInsight)
    actions = TenantScopedRepository(db, ctx, DiscoveryActionItem)
    return Worksheet(
        session=SessionOut.model_validate(session),
        subject=SubjectOut.model_validate(subject) if subject else None,
        questions=[
            SessionQuestionOut.model_validate(x)
            for x in questions.all(
                questions.query()
                .where(DiscoverySessionQuestion.session_id == session.id)
                .order_by(DiscoverySessionQuestion.position, DiscoverySessionQuestion.created_at)
            )
        ],
        insights=[
            InsightOut.model_validate(x)
            for x in insights.all(
                insights.query().where(DiscoveryInsight.session_id == session.id).order_by(DiscoveryInsight.created_at)
            )
        ],
        action_items=[
            ActionItemOut.model_validate(x)
            for x in actions.all(
                actions.query()
                .where(DiscoveryActionItem.session_id == session.id)
                .order_by(DiscoveryActionItem.created_at)
            )
        ],
    )


# --- exports -----------------------------------------------------------------

LABELS: dict[Lang, dict[str, str]] = {
    "ko": {
        "type": "유형",
        "interview": "현장 인터뷰",
        "coaching": "코칭",
        "date": "일자",
        "subject": "대상자",
        "status": "상태",
        "planned": "예정",
        "in_progress": "진행 중",
        "done": "완료",
        "summary": "요약",
        "questions": "질문과 답변",
        "follow_ups": "후속 질문",
        "no_answer": "(답변 없음)",
        "insights": "인사이트",
        "actions": "액션 아이템",
        "title": "항목",
        "assignee": "담당자",
        "due": "기한",
        "open": "미착수",
        "cancelled": "취소",
        "session": "세션",
        "insight": "인사이트",
    },
    "en": {
        "type": "Type",
        "interview": "Field interview",
        "coaching": "Coaching",
        "date": "Date",
        "subject": "Subject",
        "status": "Status",
        "planned": "Planned",
        "in_progress": "In progress",
        "done": "Done",
        "summary": "Summary",
        "questions": "Questions and answers",
        "follow_ups": "Follow-up questions",
        "no_answer": "(no answer)",
        "insights": "Insights",
        "actions": "Action items",
        "title": "Item",
        "assignee": "Assignee",
        "due": "Due",
        "open": "Open",
        "cancelled": "Cancelled",
        "session": "Session",
        "insight": "Insight",
    },
}


def _md_cell(value: object) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


def _quote(text: str) -> list[str]:
    return [f"> {line}" if line else ">" for line in text.splitlines()]


def _record_export(ctx: TenantContext, db: Session, action: str, target_type: str, target_id: str | None) -> None:
    record(
        db,
        action=action,
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type=target_type,
        target_id=target_id,
        ip=ctx.ip,
    )
    db.commit()


def export_markdown(ctx: TenantContext, db: Session, session: DiscoverySession, lang: Lang) -> str:
    ws = worksheet(ctx, db, session)
    lb = LABELS[lang]
    s = ws.session
    lines = [f"# {s.title}", ""]
    lines.append(f"- {lb['type']}: {lb.get(s.type, s.type)}")
    if s.session_date:
        lines.append(f"- {lb['date']}: {s.session_date.isoformat()}")
    if ws.subject:
        extra = ", ".join(x for x in (ws.subject.department, ws.subject.job_title) if x)
        lines.append(f"- {lb['subject']}: {ws.subject.name}" + (f" ({extra})" if extra else ""))
    lines.append(f"- {lb['status']}: {lb.get(s.status, s.status)}")
    if s.summary:
        lines += ["", f"## {lb['summary']}", "", s.summary]
    by_question: dict[str | None, list[InsightOut]] = {}
    for insight in ws.insights:
        by_question.setdefault(insight.session_question_id, []).append(insight)
    lines += ["", f"## {lb['questions']}"]
    for n, q in enumerate(ws.questions, start=1):
        lines += ["", f"### {n}. {q.text}", ""]
        lines += _quote(q.answer) if q.answer else [lb["no_answer"]]
        if q.follow_ups:
            lines += ["", f"*{lb['follow_ups']}*: " + " / ".join(q.follow_ups)]
        for insight in by_question.get(q.id, []):
            tags = " ".join(f"`#{t}`" for t in insight.tags)
            lines.append(f"- **{lb['insight']}**: {insight.text}" + (f" {tags}" if tags else ""))
    if ws.insights:
        lines += ["", f"## {lb['insights']}", ""]
        for insight in ws.insights:
            tags = " ".join(f"`#{t}`" for t in insight.tags)
            lines.append(f"- {insight.text}" + (f" {tags}" if tags else ""))
    if ws.action_items:
        lines += ["", f"## {lb['actions']}", ""]
        lines.append(f"| {lb['title']} | {lb['assignee']} | {lb['due']} | {lb['status']} |")
        lines.append("| --- | --- | --- | --- |")
        for a in ws.action_items:
            due = a.due.isoformat() if a.due else ""
            lines.append(
                f"| {_md_cell(a.title)} | {_md_cell(a.assignee)} | {due} | {_md_cell(lb.get(a.status, a.status))} |"
            )
    _record_export(ctx, db, "discoveryq.session_export", "discovery_session", session.id)
    return "\n".join(lines) + "\n"


def export_action_items_csv(
    ctx: TenantContext,
    db: Session,
    *,
    engagement_id: str | None,
    session_id: str | None,
    status: str | None,
    lang: Lang,
) -> str:
    lb = LABELS[lang]
    items = TenantScopedRepository(db, ctx, DiscoveryActionItem).all(
        action_item_filter(ctx, db, engagement_id=engagement_id, session_id=session_id, status=status).order_by(
            DiscoveryActionItem.created_at
        )
    )
    sessions = {s.id: s for s in TenantScopedRepository(db, ctx, DiscoverySession).all()}
    insights = {i.id: i.text for i in TenantScopedRepository(db, ctx, DiscoveryInsight).all()}
    rows = []
    for a in items:
        sess = sessions.get(a.session_id)
        rows.append(
            [
                sess.title if sess else "",
                sess.session_date.isoformat() if sess and sess.session_date else "",
                a.title,
                a.assignee,
                a.due.isoformat() if a.due else "",
                lb.get(a.status, a.status),
                insights.get(a.insight_id or "", ""),
            ]
        )
    header = [lb["session"], lb["date"], lb["title"], lb["assignee"], lb["due"], lb["status"], lb["insight"]]
    text = csv_text(header, rows)
    _record_export(ctx, db, "discoveryq.action_items_export", "discovery_action_item", None)
    return text
