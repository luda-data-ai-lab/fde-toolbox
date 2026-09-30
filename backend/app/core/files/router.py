from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.auth.deps import DB
from app.core.errors import not_found
from app.core.files import service
from app.core.files.models import StoredFile
from app.core.pagination import Page
from app.core.schemas import ORMModel
from app.core.tenancy.deps import Ctx, WriteCtx, path_entity, repo

router = APIRouter(prefix="/t/{tenant_id}/files", tags=["files"])

FileDep = Annotated[StoredFile, Depends(path_entity(StoredFile, "file_id"))]


class FileOut(ORMModel):
    tenant_id: str
    owner_type: str | None
    owner_id: str | None
    filename: str
    mime: str
    size: int
    sha256: str


@router.get("", response_model=Page[FileOut])
def list_files(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
) -> Page[FileOut]:
    r = repo(db, ctx, StoredFile)
    stmt = r.query()
    if owner_type:
        stmt = stmt.where(StoredFile.owner_type == owner_type)
    if owner_id:
        stmt = stmt.where(StoredFile.owner_id == owner_id)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[FileOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("", response_model=FileOut, status_code=201)
def upload_file(
    ctx: WriteCtx,
    db: DB,
    file: Annotated[UploadFile, File()],
    owner_type: Annotated[str | None, Form()] = None,
    owner_id: Annotated[str | None, Form()] = None,
) -> FileOut:
    return FileOut.model_validate(service.upload(ctx, db, file, owner_type, owner_id))


@router.get("/{file_id}", response_model=FileOut)
def get_file(obj: FileDep) -> FileOut:
    return FileOut.model_validate(obj)


@router.get("/{file_id}/download")
def download_file(obj: FileDep) -> FileResponse:
    path = service.absolute_path(obj)
    if not path.exists():
        raise not_found()
    return FileResponse(path, media_type=obj.mime, filename=obj.filename)


@router.delete("/{file_id}", status_code=204)
def delete_file(obj: FileDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete(ctx, db, obj)
    return Response(status_code=204)
