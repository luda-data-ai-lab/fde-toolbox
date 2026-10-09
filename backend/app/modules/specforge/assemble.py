"""Rule-based assembly of Spec.md / Devin.md drafts from engagement outputs (no LLM).

Other modules' tables are read through `Base.metadata.tables` with an explicit tenant filter,
because modules must not import each other.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Table, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy.context import TenantContext
from app.core.tenants.models import Engagement
from app.db.base import Base
from app.modules.specforge.schemas import SpecSources, TemplateOut

DATA_MODEL_DIRECTIVE = (
    "데이터 모델의 테이블·컬럼·화면 용어는 아래 용어 사전의 표준 용어를 따른다. "
    "부서별 호칭은 표시명이나 검색어로만 쓴다."
)


@dataclass
class SessionInfo:
    title: str
    date: str | None
    summary: str | None
    insights: list[tuple[str, list[str]]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FlowInfo:
    title: str
    kind: str
    perspective: str
    description: str | None
    lanes: list[str]
    steps: list[str]
    systems: list[str]


@dataclass
class Inputs:
    engagement: Engagement
    requirements: str | None = None
    sessions: list[SessionInfo] = field(default_factory=list)
    flows: list[FlowInfo] = field(default_factory=list)
    interfaces: list[dict[str, Any]] | None = None
    glossary: list[dict[str, Any]] | None = None
    rules: list[tuple[str, list[str]]] = field(default_factory=list)


def _t(name: str) -> Table:
    return Base.metadata.tables[name]


def _rows_in_engagement(
    db: Session, ctx: TenantContext, name: str, ids: list[str], engagement_id: str, field_name: str
) -> list[Any]:
    if not ids:
        return []
    t = _t(name)
    rows = db.execute(
        select(t).where(t.c.tenant_id == ctx.tenant_id, t.c.engagement_id == engagement_id, t.c.id.in_(set(ids)))
    ).all()
    if len(rows) != len(set(ids)):
        raise AppError(422, "invalid_reference", detail={"field": field_name})
    order = {i: n for n, i in enumerate(ids)}
    return sorted(rows, key=lambda r: order[r.id])


def validate_sources(db: Session, ctx: TenantContext, engagement_id: str, sources: SpecSources) -> None:
    _rows_in_engagement(
        db, ctx, "discovery_sessions", sources.discovery_session_ids, engagement_id, "sources.discovery_session_ids"
    )
    _rows_in_engagement(db, ctx, "flows", sources.flow_ids, engagement_id, "sources.flow_ids")


def _system_names(db: Session, ctx: TenantContext, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    t = _t("systems")
    return {
        r.id: r.name
        for r in db.execute(select(t.c.id, t.c.name).where(t.c.tenant_id == ctx.tenant_id, t.c.id.in_(ids)))
    }


def _sessions(db: Session, ctx: TenantContext, engagement_id: str, ids: list[str]) -> list[SessionInfo]:
    rows = _rows_in_engagement(db, ctx, "discovery_sessions", ids, engagement_id, "sources.discovery_session_ids")
    if not rows:
        return []
    out = {r.id: SessionInfo(r.title, r.session_date.isoformat() if r.session_date else None, r.summary) for r in rows}
    ins, act = _t("discovery_insights"), _t("discovery_action_items")
    for r in db.execute(
        select(ins).where(ins.c.tenant_id == ctx.tenant_id, ins.c.session_id.in_(out)).order_by(ins.c.created_at)
    ):
        out[r.session_id].insights.append((r.text, list(r.tags or [])))
    for r in db.execute(
        select(act).where(act.c.tenant_id == ctx.tenant_id, act.c.session_id.in_(out)).order_by(act.c.created_at)
    ):
        out[r.session_id].actions.append(
            {"title": r.title, "assignee": r.assignee, "due": r.due.isoformat() if r.due else None, "status": r.status}
        )
    return list(out.values())


def _flows(db: Session, ctx: TenantContext, engagement_id: str, ids: list[str]) -> list[FlowInfo]:
    rows = _rows_in_engagement(db, ctx, "flows", ids, engagement_id, "sources.flow_ids")
    graphs = [r.graph if isinstance(r.graph, dict) else {} for r in rows]
    system_ids = {str(n["system_id"]) for g in graphs for n in g.get("nodes", []) if n.get("system_id")}
    names = _system_names(db, ctx, system_ids)
    result = []
    for r, g in zip(rows, graphs, strict=True):
        nodes = [n for n in g.get("nodes", []) if isinstance(n, dict)]
        steps = [str(n.get("label")) for n in nodes if n.get("type") in {"task", "decision"} and n.get("label")]
        systems = sorted({names[str(n["system_id"])] for n in nodes if n.get("system_id") in names})
        lanes = [str(x) for x in g.get("lanes", [])]
        result.append(FlowInfo(r.title, r.kind, r.perspective, r.description, lanes, steps, systems))
    return result


def _interfaces(db: Session, ctx: TenantContext) -> list[dict[str, Any]]:
    t = _t("interfaces")
    rows = db.execute(select(t).where(t.c.tenant_id == ctx.tenant_id).order_by(t.c.if_code)).all()
    names = _system_names(db, ctx, {r.source_system_id for r in rows} | {r.target_system_id for r in rows})
    return [
        {
            "code": r.if_code,
            "name": r.name,
            "source": names.get(r.source_system_id, "?"),
            "target": names.get(r.target_system_id, "?"),
            "type": r.link_type,
            "schedule": r.schedule,
        }
        for r in rows
    ]


def _glossary(db: Session, ctx: TenantContext) -> list[dict[str, Any]]:
    terms, aliases = _t("onto_terms"), _t("onto_term_aliases")
    rows = db.execute(
        select(terms).where(terms.c.tenant_id == ctx.tenant_id, terms.c.status == "confirmed").order_by(terms.c.term)
    ).all()
    by_term: dict[str, list[str]] = defaultdict(list)
    for a in db.execute(
        select(aliases).where(aliases.c.tenant_id == ctx.tenant_id, aliases.c.term_id.in_([r.id for r in rows]))
    ):
        by_term[a.term_id].append(f"{a.alias} ({a.department})" if a.department else a.alias)
    return [
        {"term": r.term, "abbreviation": r.abbreviation, "definition": r.definition, "aliases": sorted(by_term[r.id])}
        for r in rows
    ]


def collect(
    db: Session, ctx: TenantContext, engagement: Engagement, sources: SpecSources, rules: list[tuple[str, list[str]]]
) -> Inputs:
    return Inputs(
        engagement=engagement,
        requirements=(sources.requirements or "").strip() or None,
        sessions=_sessions(db, ctx, engagement.id, sources.discovery_session_ids),
        flows=_flows(db, ctx, engagement.id, sources.flow_ids),
        interfaces=_interfaces(db, ctx) if sources.interfaces else None,
        glossary=_glossary(db, ctx) if sources.glossary else None,
        rules=rules,
    )


# --- rendering ---------------------------------------------------------------


def _cell(value: object) -> str:
    return " ".join(str(value if value is not None else "").split()).replace("|", "\\|")


def _table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _todo(rule: str | None) -> str:
    return f"> TODO: {rule}" if rule else "> TODO"


def _overview(i: Inputs) -> list[str]:
    parts = [f"과제: **{_cell(i.engagement.name)}**"]
    if i.engagement.description:
        parts.append(i.engagement.description.strip())
    if i.requirements:
        parts.append(i.requirements)
    return parts


def _glossary_md(i: Inputs) -> list[str]:
    if i.glossary is None:
        return []
    if not i.glossary:
        return ["(확정된 용어가 없습니다.)"]
    rows: list[list[object]] = [
        [g["term"], g["abbreviation"], g["definition"], ", ".join(g["aliases"])] for g in i.glossary
    ]
    return [_table(["표준 용어", "약어", "정의", "부서별 호칭"], rows)]


def _structure_md(i: Inputs) -> list[str]:
    out: list[str] = []
    for f in i.flows:
        lines = [f"**{_cell(f.title)}** ({f.kind}, {f.perspective})"]
        if f.description:
            lines.append(f.description.strip())
        if f.lanes:
            lines.append(f"- 레인: {', '.join(f.lanes)}")
        if f.steps:
            lines.append(f"- 주요 단계: {' → '.join(f.steps)}")
        if f.systems:
            lines.append(f"- 관련 시스템: {', '.join(f.systems)}")
        out.append("\n".join(lines))
    if i.interfaces is not None:
        rows: list[list[object]] = [
            [x["code"], x["name"], x["source"], x["target"], x["type"], x["schedule"]] for x in i.interfaces
        ]
        out.append(
            _table(["I/F 코드", "이름", "송신", "수신", "방식", "주기"], rows) if rows else "(등록된 I/F가 없습니다.)"
        )
    return out


def _features_md(i: Inputs) -> list[str]:
    out: list[str] = []
    for s in i.sessions:
        head = f"**{_cell(s.title)}**" + (f" ({s.date})" if s.date else "")
        lines = [head]
        if s.summary:
            lines.append(s.summary.strip())
        lines += [f"- {_cell(text)}" + (f" `{'`, `'.join(tags)}`" if tags else "") for text, tags in s.insights]
        out.append("\n".join(lines))
    return out


def _actions_md(i: Inputs) -> list[str]:
    rows: list[list[object]] = [
        [a["title"], a["assignee"], a["due"], a["status"]] for s in i.sessions for a in s.actions
    ]
    return [_table(["항목", "담당", "기한", "상태"], rows)] if rows else []


def _rules_md(i: Inputs) -> list[str]:
    out = []
    for title, rules in i.rules:
        out.append(f"**{_cell(title)}**\n" + "\n".join(f"- {r}" for r in rules))
    return out


def _data_model_md(i: Inputs) -> list[str]:
    glossary = _glossary_md(i)
    return [DATA_MODEL_DIRECTIVE, *glossary] if glossary else []


SECTION_BUILDERS = {
    "overview": _overview,
    "goal": _overview,
    "terms": _glossary_md,
    "structure": _structure_md,
    "features": _features_md,
    "rules": _rules_md,
    "data_model": _data_model_md,
    "steps": _actions_md,
}


def render(template: TemplateOut, title: str, inputs: Inputs) -> str:
    """Fill each template section from its builder; sections without input keep the rule as a TODO."""
    out = [f"# {title}", ""]
    for section in template.sections:
        builder = SECTION_BUILDERS.get(section.key)
        body = builder(inputs) if builder else []
        out += [f"## {section.title}", "", *("\n\n".join(body) if body else _todo(section.rule)).split("\n"), ""]
    return "\n".join(out).rstrip() + "\n"
