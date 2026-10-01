from typing import Any

from fastapi import UploadFile
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.exports import csv_text
from app.core.files.service import read_upload, store_bytes
from app.core.systems.models import System
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.modules.interfaces import excel
from app.modules.interfaces.models import Interface, InterfaceUpload
from app.modules.interfaces.schemas import (
    ApplyIn,
    GraphEdge,
    GraphNode,
    InterfaceDashboard,
    InterfaceGraph,
    InterfaceIn,
    InterfacePatch,
    SystemCount,
)

WORKBOOK_EXTENSIONS = {"xlsx", "xlsm"}
FIELDS = [k for k, _ in excel.IF_COLUMNS]


def _norm(name: str) -> str:
    return " ".join(name.split()).lower()


def _system_index(db: Session, ctx: TenantContext) -> dict[str, str]:
    """Lookup of system id by normalised name or short name (names win over short names)."""
    systems = TenantScopedRepository(db, ctx, System).all()
    index: dict[str, str] = {}
    for s in systems:
        if s.short_name:
            index.setdefault(_norm(s.short_name), s.id)
    for s in systems:
        index[_norm(s.name)] = s.id
    return index


def _check_refs(db: Session, ctx: TenantContext, *system_ids: str | None) -> None:
    systems = TenantScopedRepository(db, ctx, System)
    for field, sid in zip(("source_system_id", "target_system_id"), system_ids, strict=True):
        systems.ensure_ref(sid, field)


def _ensure_code_free(db: Session, ctx: TenantContext, if_code: str, exclude_id: str | None = None) -> None:
    r = TenantScopedRepository(db, ctx, Interface)
    stmt = r.query().where(Interface.if_code == if_code)
    if exclude_id:
        stmt = stmt.where(Interface.id != exclude_id)
    if r.all(stmt):
        raise AppError(409, "if_code_taken")


@audited("interface.create", "interface")
def create_interface(ctx: TenantContext, db: Session, body: InterfaceIn) -> Interface:
    _check_refs(db, ctx, body.source_system_id, body.target_system_id)
    _ensure_code_free(db, ctx, body.if_code)
    return TenantScopedRepository(db, ctx, Interface).create(**body.model_dump())


@audited("interface.update", "interface")
def update_interface(ctx: TenantContext, db: Session, obj: Interface, body: InterfacePatch) -> Interface:
    data = body.model_dump(exclude_unset=True)
    for key in ("if_code", "name", "source_system_id", "target_system_id", "link_type", "status"):
        if key in data and data[key] is None:
            raise AppError(422, "validation_error", detail={"field": key})
    _check_refs(db, ctx, data.get("source_system_id"), data.get("target_system_id"))
    if "if_code" in data:
        _ensure_code_free(db, ctx, data["if_code"], exclude_id=obj.id)
    return TenantScopedRepository(db, ctx, Interface).update(obj, **data)


@audited("interface.delete", "interface")
def delete_interface(ctx: TenantContext, db: Session, obj: Interface) -> str:
    TenantScopedRepository(db, ctx, Interface).delete(obj)
    return obj.id


def _validate_row(row: excel.SheetRow) -> tuple[dict[str, Any], list[dict[str, str]]]:
    v = row.values
    errors: list[dict[str, str]] = [{"field": f, "code": "required"} for f in excel.IF_REQUIRED if v.get(f) is None]
    data: dict[str, Any] = {f: v.get(f) for f in FIELDS}
    link_type = excel.normalize_link_type(v.get("link_type"))
    if link_type is None:
        errors.append({"field": "link_type", "code": "unknown_link_type"})
    data["link_type"] = link_type
    status = excel.normalize_status(v.get("status"))
    if status is None:
        errors.append({"field": "status", "code": "unknown_status"})
    data["status"] = status
    volume = v.get("daily_volume")
    if volume is not None:
        cleaned = volume.replace(",", "")
        if cleaned.isdigit():
            data["daily_volume"] = int(cleaned)
        else:
            errors.append({"field": "daily_volume", "code": "invalid_number"})
            data["daily_volume"] = None
    for f, limit in (("if_code", 100), ("name", 300), ("schedule", 100), ("owner", 100)):
        value = data.get(f)
        if isinstance(value, str) and len(value) > limit:
            errors.append({"field": f, "code": "too_long"})
    return data, errors


def _sheet_systems(parsed: excel.ParsedWorkbook) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in parsed.systems:
        name = row.values.get("name")
        if name is None:
            continue
        info = {
            "name": name[:200],
            "short_name": (row.values.get("short_name") or None),
            "type": excel.normalize_system_type(row.values.get("type")),
            "owner_dept": row.values.get("owner_dept"),
            "hosting": excel.normalize_hosting(row.values.get("hosting")),
            "db_type": row.values.get("db_type"),
            "notes": row.values.get("notes"),
        }
        out[_norm(name)] = info
        if info["short_name"]:
            out.setdefault(_norm(info["short_name"]), info)
    return out


def validate_workbook(db: Session, ctx: TenantContext, filename: str, data: bytes) -> dict[str, Any]:
    try:
        parsed = excel.parse_workbook(data)
    except excel.WorkbookError as exc:
        raise AppError(400, exc.code, detail=exc.detail) from exc
    index = _system_index(db, ctx)
    sheet_systems = _sheet_systems(parsed)
    existing = set(db.scalars(select(Interface.if_code).where(Interface.tenant_id == ctx.tenant_id)).all())
    seen: set[str] = set()
    unregistered: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    summary = {"total": 0, "valid": 0, "invalid": 0, "create": 0, "update": 0}
    for row in parsed.interfaces:
        values, errors = _validate_row(row)
        code = values.get("if_code")
        if code is not None:
            if code in seen:
                errors.append({"field": "if_code", "code": "duplicate_in_file"})
            seen.add(code)
        missing: list[str] = []
        for f in ("source", "target"):
            name = values.get(f)
            if name is not None and _norm(name) not in index:
                missing.append(name)
                key = _norm(name)
                entry = unregistered.setdefault(
                    key,
                    {
                        "name": name,
                        "rows": 0,
                        "in_system_sheet": key in sheet_systems,
                        "system": sheet_systems.get(key, {"name": name[:200], "type": "OTHER"}),
                    },
                )
                entry["rows"] += 1
        action = "error" if errors else ("update" if code in existing else "create")
        rows.append({"row": row.row, "values": values, "errors": errors, "unregistered": missing, "action": action})
        summary["total"] += 1
        if errors:
            summary["invalid"] += 1
        else:
            summary["valid"] += 1
            summary[action] += 1
    return {
        "filename": filename,
        "summary": summary,
        "rows": rows,
        "unregistered_systems": list(unregistered.values()),
    }


@audited("interface.upload", "interface_upload")
def upload_workbook(ctx: TenantContext, db: Session, file: UploadFile) -> InterfaceUpload:
    name, data = read_upload(file, WORKBOOK_EXTENSIONS)
    result = validate_workbook(db, ctx, name, data)
    stored = store_bytes(ctx, db, name, data, "interface_upload", None)
    upload = TenantScopedRepository(db, ctx, InterfaceUpload).create(file_id=stored.id, result=result)
    stored.owner_id = upload.id
    db.flush()
    return upload


def _create_systems(db: Session, ctx: TenantContext, upload: InterfaceUpload, names: list[str]) -> list[str]:
    wanted = {_norm(n) for n in names}
    systems = TenantScopedRepository(db, ctx, System)
    index = _system_index(db, ctx)
    created: list[str] = []
    for entry in upload.result.get("unregistered_systems", []):
        key = _norm(str(entry["name"]))
        if key not in wanted or key in index:
            continue
        info = dict(entry.get("system") or {"name": entry["name"], "type": "OTHER"})
        sys_obj = systems.create(
            **{k: info.get(k) for k in ("name", "short_name", "owner_dept", "db_type", "notes", "hosting")},
            type=info.get("type") or "OTHER",
        )
        index[key] = sys_obj.id
        index[_norm(sys_obj.name)] = sys_obj.id
        created.append(sys_obj.name)
    return created


@audited("interface.upload_apply", "interface_upload")
def apply_upload(ctx: TenantContext, db: Session, upload: InterfaceUpload, body: ApplyIn) -> InterfaceUpload:
    if upload.status != "validated":
        raise AppError(409, "upload_already_applied")
    systems_created = _create_systems(db, ctx, upload, body.register_systems)
    index = _system_index(db, ctx)
    repo = TenantScopedRepository(db, ctx, Interface)
    by_code = {i.if_code: i for i in repo.all()}
    created = updated = 0
    skipped: list[dict[str, Any]] = []
    for row in upload.result.get("rows", []):
        if row["errors"]:
            continue
        v = row["values"]
        src, dst = index.get(_norm(v["source"])), index.get(_norm(v["target"]))
        if src is None or dst is None:
            skipped.append({"row": row["row"], "if_code": v["if_code"], "code": "unregistered_system"})
            continue
        values = {f: v.get(f) for f in FIELDS if f not in ("source", "target")}
        values.update(source_system_id=src, target_system_id=dst)
        current = by_code.get(v["if_code"])
        if current is None:
            by_code[v["if_code"]] = repo.create(**values)
            created += 1
        else:
            repo.update(current, **values)
            updated += 1
    result = dict(upload.result)
    result["applied"] = {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "systems_created": systems_created,
    }
    return TenantScopedRepository(db, ctx, InterfaceUpload).update(upload, status="applied", result=result)


def filtered(
    ctx: TenantContext,
    db: Session,
    *,
    system_id: str | None = None,
    link_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> Select[Interface]:
    stmt = TenantScopedRepository(db, ctx, Interface).query()
    if system_id:
        stmt = stmt.where(or_(Interface.source_system_id == system_id, Interface.target_system_id == system_id))
    if link_type:
        stmt = stmt.where(Interface.link_type == link_type)
    if status:
        stmt = stmt.where(Interface.status == status)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Interface.if_code).like(like), func.lower(Interface.name).like(like)))
    return stmt


def _counts(db: Session, ctx: TenantContext, column: InstrumentedAttribute[str]) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(Interface.tenant_id == ctx.tenant_id).group_by(column)).all()
    return {str(k): int(n) for k, n in rows}


def dashboard(ctx: TenantContext, db: Session) -> InterfaceDashboard:
    out_counts = _counts(db, ctx, Interface.source_system_id)
    in_counts = _counts(db, ctx, Interface.target_system_id)
    systems = TenantScopedRepository(db, ctx, System).all()
    by_system = [
        SystemCount(system_id=s.id, name=s.name, outgoing=out_counts.get(s.id, 0), incoming=in_counts.get(s.id, 0))
        for s in systems
    ]
    by_system.sort(key=lambda c: (-(c.outgoing + c.incoming), c.name))
    return InterfaceDashboard(
        total=sum(out_counts.values()),
        by_link_type=_counts(db, ctx, Interface.link_type),
        by_status=_counts(db, ctx, Interface.status),
        by_system=by_system,
    )


def graph(
    ctx: TenantContext, db: Session, *, link_type: str | None = None, status: str | None = None
) -> InterfaceGraph:
    interfaces = TenantScopedRepository(db, ctx, Interface).all(
        filtered(ctx, db, link_type=link_type, status=status).order_by(Interface.if_code)
    )
    degree: dict[str, int] = {}
    for i in interfaces:
        degree[i.source_system_id] = degree.get(i.source_system_id, 0) + 1
        degree[i.target_system_id] = degree.get(i.target_system_id, 0) + 1
    systems = TenantScopedRepository(db, ctx, System).all()
    return InterfaceGraph(
        nodes=[
            GraphNode(id=s.id, name=s.name, short_name=s.short_name, type=s.type, degree=degree.get(s.id, 0))
            for s in sorted(systems, key=lambda s: s.name)
        ],
        edges=[
            GraphEdge(
                id=i.id,
                source=i.source_system_id,
                target=i.target_system_id,
                if_code=i.if_code,
                name=i.name,
                link_type=i.link_type,
                status=i.status,
            )
            for i in interfaces
        ],
    )


def _export_rows(ctx: TenantContext, db: Session) -> tuple[list[list[Any]], list[System]]:
    systems = TenantScopedRepository(db, ctx, System).all()
    names = {s.id: s.name for s in systems}
    interfaces = TenantScopedRepository(db, ctx, Interface).all(
        TenantScopedRepository(db, ctx, Interface).query().order_by(Interface.if_code)
    )
    rows = [
        [
            i.if_code,
            i.name,
            names.get(i.source_system_id),
            names.get(i.target_system_id),
            excel.LINK_TYPE_LABELS.get(i.link_type, i.link_type),
            i.schedule,
            i.description,
            i.daily_volume,
            i.owner,
            excel.STATUS_LABELS.get(i.status, i.status),
            i.notes,
        ]
        for i in interfaces
    ]
    return rows, sorted(systems, key=lambda s: s.name)


def _record_export(ctx: TenantContext, db: Session, fmt: str) -> None:
    record(
        db,
        action="interface.export",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="interface",
        detail={"format": fmt},
        ip=ctx.ip,
    )
    db.commit()


def template_workbook() -> bytes:
    return excel.build_workbook([], [])


def export_workbook(ctx: TenantContext, db: Session) -> bytes:
    rows, systems = _export_rows(ctx, db)
    system_rows = [
        [
            s.name,
            s.short_name,
            s.type,
            s.owner_dept,
            excel.HOSTING_LABELS.get(s.hosting or "", s.hosting),
            s.db_type,
            None,
            s.notes,
        ]
        for s in systems
    ]
    data = excel.build_workbook(rows, system_rows)
    _record_export(ctx, db, "xlsx")
    return data


def export_csv(ctx: TenantContext, db: Session) -> str:
    rows, _ = _export_rows(ctx, db)
    text = csv_text([h for _, h in excel.IF_COLUMNS], rows)
    _record_export(ctx, db, "csv")
    return text
