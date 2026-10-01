from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.auth.deps import DB
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.interfaces import service
from app.modules.interfaces.models import Interface, InterfaceUpload
from app.modules.interfaces.schemas import (
    ApplyIn,
    InterfaceDashboard,
    InterfaceGraph,
    InterfaceIn,
    InterfaceOut,
    InterfacePatch,
    InterfaceStatus,
    LinkType,
    UploadOut,
)

router = APIRouter(prefix="/t/{tenant_id}/interfaces", tags=["interfaces"])

InterfaceDep = Annotated[Interface, Depends(path_entity(Interface, "interface_id"))]
UploadDep = Annotated[InterfaceUpload, Depends(path_entity(InterfaceUpload, "upload_id"))]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment(data: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content=data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("", response_model=Page[InterfaceOut])
def list_interfaces(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    system_id: str | None = None,
    link_type: LinkType | None = None,
    status: InterfaceStatus | None = None,
    q: str | None = None,
) -> Page[InterfaceOut]:
    stmt = service.filtered(ctx, db, system_id=system_id, link_type=link_type, status=status, q=q)
    rows, nxt = repo(db, ctx, Interface).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[InterfaceOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("", response_model=InterfaceOut, status_code=201)
def create_interface(body: InterfaceIn, ctx: WriteCtx, db: DB) -> InterfaceOut:
    return InterfaceOut.model_validate(service.create_interface(ctx, db, body))


@router.get("/dashboard", response_model=InterfaceDashboard)
def dashboard(ctx: Ctx, db: DB) -> InterfaceDashboard:
    return service.dashboard(ctx, db)


@router.get("/graph", response_model=InterfaceGraph)
def graph(ctx: Ctx, db: DB, link_type: LinkType | None = None, status: InterfaceStatus | None = None) -> InterfaceGraph:
    return service.graph(ctx, db, link_type=link_type, status=status)


@router.get("/template.xlsx")
def template(ctx: Ctx) -> Response:
    return _attachment(service.template_workbook(), XLSX, "interface-template.xlsx")


@router.get("/export.xlsx")
def export_xlsx(ctx: ExportCtx, db: DB) -> Response:
    return _attachment(service.export_workbook(ctx, db), XLSX, "interfaces.xlsx")


@router.get("/export.csv")
def export_csv(ctx: ExportCtx, db: DB) -> Response:
    return _attachment(service.export_csv(ctx, db), "text/csv; charset=utf-8", "interfaces.csv")


@router.post("/uploads", response_model=UploadOut, status_code=201)
def upload(ctx: WriteCtx, db: DB, file: Annotated[UploadFile, File()]) -> UploadOut:
    return UploadOut.model_validate(service.upload_workbook(ctx, db, file))


@router.get("/uploads/{upload_id}", response_model=UploadOut)
def get_upload(obj: UploadDep) -> UploadOut:
    return UploadOut.model_validate(obj)


@router.post("/uploads/{upload_id}/apply", response_model=UploadOut)
def apply_upload(obj: UploadDep, body: ApplyIn, ctx: WriteCtx, db: DB) -> UploadOut:
    return UploadOut.model_validate(service.apply_upload(ctx, db, obj, body))


@router.get("/{interface_id}", response_model=InterfaceOut)
def get_interface(obj: InterfaceDep) -> InterfaceOut:
    return InterfaceOut.model_validate(obj)


@router.patch("/{interface_id}", response_model=InterfaceOut)
def update_interface(obj: InterfaceDep, body: InterfacePatch, ctx: WriteCtx, db: DB) -> InterfaceOut:
    return InterfaceOut.model_validate(service.update_interface(ctx, db, obj, body))


@router.delete("/{interface_id}", status_code=204)
def delete_interface(obj: InterfaceDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_interface(ctx, db, obj)
    return Response(status_code=204)
