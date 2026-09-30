"""Tenant-wide export/import as a ZIP bundle (manifest.json + attachment files)."""

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Table, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit.models import AuditLog
from app.core.audit.service import record
from app.core.errors import AppError, bad_request
from app.core.files.models import StoredFile
from app.core.serialization import row_from_json, row_to_json, table_of
from app.core.tenancy.context import Principal, TenantContext
from app.core.tenants.models import Tenant
from app.db.base import Base, TenantScopedModel, new_id
from app.db.session import tenant_scope

SCHEMA_VERSION = 1
KIND = "tenant_export"
MAX_UNCOMPRESSED_BYTES = 2 * 1024**3


def tenant_tables() -> list[Table]:
    """Tenant-scoped tables plus the tenant's audit trail, in FK dependency order."""
    names = {table_of(m.class_).name for m in Base.registry.mappers if issubclass(m.class_, TenantScopedModel)}
    names.add(AuditLog.__tablename__)
    return [t for t in Base.metadata.sorted_tables if t.name in names]


def export_tenant(ctx: TenantContext, db: Session) -> bytes:
    tenant = db.get(Tenant, ctx.tenant_id)
    if tenant is None:
        raise AppError(404, "not_found")
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in tenant_tables():
        rows = db.execute(select(table).where(table.c.tenant_id == ctx.tenant_id)).mappings().all()
        tables[table.name] = [row_to_json(table, dict(r)) for r in rows]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "exported_at": datetime.now(UTC).isoformat(),
        "tenant": row_to_json(table_of(Tenant), _tenant_row(db, tenant.id)),
        "tables": tables,
    }
    files_root = get_settings().data_dir / "files"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for f in tables.get(StoredFile.__tablename__, []):
            path = files_root / f["storage_path"]
            if path.exists():
                zf.write(path, f"files/{f['id']}")
    record(
        db,
        action="tenant.export",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="tenant",
        target_id=ctx.tenant_id,
        ip=ctx.ip,
    )
    db.commit()
    return buf.getvalue()


def _tenant_row(db: Session, tenant_id: str) -> dict[str, Any]:
    table = table_of(Tenant)
    return dict(db.execute(select(table).where(table.c.id == tenant_id)).mappings().one())


def _remap(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, str):
        return ids.get(value, value)
    if isinstance(value, list):
        return [_remap(v, ids) for v in value]
    if isinstance(value, dict):
        return {k: _remap(v, ids) for k, v in value.items()}
    return value


def _read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    if sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED_BYTES:
        raise AppError(413, "file_too_large")
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except (KeyError, ValueError) as exc:
        raise bad_request("invalid_bundle") from exc
    if not isinstance(manifest, dict) or manifest.get("kind") != KIND:
        raise bad_request("invalid_bundle")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise bad_request("unsupported_schema_version")
    return manifest


def import_tenant(principal: Principal, db: Session, data: bytes, code: str, name: str | None) -> Tenant:
    """Create a new tenant from an export bundle. All row ids are regenerated."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise bad_request("invalid_bundle") from exc
    with zf:
        manifest = _read_manifest(zf)
        if db.scalars(select(Tenant).where(Tenant.code == code)).first():
            raise AppError(409, "tenant_code_taken")
        src = manifest.get("tenant") or {}
        tables: dict[str, list[dict[str, Any]]] = manifest.get("tables") or {}
        known = {t.name: t for t in tenant_tables()}
        if any(name_ not in known for name_ in tables):
            raise bad_request("invalid_bundle")
        new_tenant_id = new_id()
        ids: dict[str, str] = {str(src.get("id")): new_tenant_id}
        for rows in tables.values():
            for row in rows:
                ids[str(row["id"])] = new_id()
        tenant = Tenant(
            id=new_tenant_id,
            name=name or str(src.get("name") or code),
            code=code,
            deployment_mode=str(src.get("deployment_mode") or "standalone"),
            notes=src.get("notes"),
            created_by=principal.user_id,
        )
        db.add(tenant)
        db.flush()
        files_root = get_settings().data_dir / "files"
        written: list[Any] = []
        try:
            with tenant_scope(db, new_tenant_id):
                for table_name, table in known.items():
                    rows = tables.get(table_name, [])
                    if not rows:
                        continue
                    values = [row_from_json(table, _remap(r, ids)) for r in rows]
                    for v in values:
                        v["tenant_id"] = new_tenant_id
                    if table_name == StoredFile.__tablename__:
                        for old, v in zip(rows, values, strict=True):
                            v["storage_path"] = f"{new_tenant_id}/{v['id']}"
                            target = files_root / v["storage_path"]
                            target.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                target.write_bytes(zf.read(f"files/{old['id']}"))
                            except KeyError:
                                target.write_bytes(b"")
                            written.append(target)
                    db.execute(insert(table), values)
            record(
                db,
                action="tenant.import",
                actor_id=principal.user_id,
                tenant_id=new_tenant_id,
                target_type="tenant",
                target_id=new_tenant_id,
                detail={"source_code": src.get("code")},
                ip=principal.ip,
            )
            with tenant_scope(db, new_tenant_id):
                db.commit()
        except Exception:
            db.rollback()
            for path in written:
                path.unlink(missing_ok=True)
            raise
    return tenant
