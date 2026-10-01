import hashlib
import mimetypes
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit.service import audited
from app.core.errors import AppError
from app.core.files.models import StoredFile
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.db.base import new_id

CHUNK = 1024 * 1024


def tenant_dir(tenant_id: str) -> Path:
    return get_settings().data_dir / "files" / tenant_id


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name.strip()
    return name[:255] or "file"


def store_bytes(
    ctx: TenantContext, db: Session, filename: str, data: bytes, owner_type: str | None, owner_id: str | None
) -> StoredFile:
    name = safe_filename(filename)
    storage_rel = f"{ctx.tenant_id}/{new_id()}"
    path = get_settings().data_dir / "files" / storage_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return TenantScopedRepository(db, ctx, StoredFile).create(
        owner_type=owner_type,
        owner_id=owner_id,
        filename=name,
        mime=mimetypes.guess_type(name)[0] or "application/octet-stream",
        size=len(data),
        storage_path=storage_rel,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def read_upload(file: UploadFile, extensions: set[str] | None = None) -> tuple[str, bytes]:
    """Read an upload within the size limit; extensions default to the configured allow-list."""
    s = get_settings()
    name = safe_filename(file.filename or "file")
    allowed = s.upload_extensions if extensions is None else extensions & s.upload_extensions
    if _extension(name) not in allowed:
        raise AppError(400, "file_type_not_allowed")
    limit = s.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while chunk := file.file.read(CHUNK):
        total += len(chunk)
        if total > limit:
            raise AppError(413, "file_too_large")
        chunks.append(chunk)
    return name, b"".join(chunks)


@audited("file.upload", "file")
def upload(
    ctx: TenantContext, db: Session, file: UploadFile, owner_type: str | None, owner_id: str | None
) -> StoredFile:
    name, data = read_upload(file)
    return store_bytes(ctx, db, name, data, owner_type, owner_id)


def absolute_path(obj: StoredFile) -> Path:
    base = (get_settings().data_dir / "files").resolve()
    path = (base / obj.storage_path).resolve()
    if base not in path.parents:
        raise AppError(404, "not_found")
    return path


@audited("file.delete", "file")
def delete(ctx: TenantContext, db: Session, obj: StoredFile) -> str:
    path = absolute_path(obj)
    TenantScopedRepository(db, ctx, StoredFile).delete(obj)
    path.unlink(missing_ok=True)
    return obj.id
