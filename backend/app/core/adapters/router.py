from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.adapters import service
from app.core.adapters.models import AdapterActivation
from app.core.adapters.schemas import ActivationOut, ActivationRequestIn, AdapterOut, ApproveIn, HealthOut, ReasonIn
from app.core.auth.deps import DB
from app.core.tenancy.deps import Ctx, path_entity

router = APIRouter(prefix="/t/{tenant_id}/adapters", tags=["adapters"])

ActivationDep = Annotated[AdapterActivation, Depends(path_entity(AdapterActivation, "activation_id"))]


@router.get("", response_model=list[AdapterOut])
def list_adapters(ctx: Ctx, db: DB) -> list[AdapterOut]:
    return service.list_adapters(ctx, db)


@router.post("/activations", response_model=ActivationOut, status_code=201)
def request_activation(body: ActivationRequestIn, ctx: Ctx, db: DB) -> ActivationOut:
    return service.activation_out(service.request_activation(ctx, db, body))


@router.get("/activations/{activation_id}", response_model=ActivationOut)
def get_activation(obj: ActivationDep) -> ActivationOut:
    return service.activation_out(obj)


@router.post("/activations/{activation_id}/approve", response_model=ActivationOut)
def approve(obj: ActivationDep, body: ApproveIn, ctx: Ctx, db: DB) -> ActivationOut:
    return service.activation_out(service.approve(ctx, db, obj, body))


@router.post("/activations/{activation_id}/reject", response_model=ActivationOut)
def reject(obj: ActivationDep, body: ReasonIn, ctx: Ctx, db: DB) -> ActivationOut:
    return service.activation_out(service.reject(ctx, db, obj, body))


@router.post("/activations/{activation_id}/deactivate", response_model=ActivationOut)
def deactivate(obj: ActivationDep, body: ReasonIn, ctx: Ctx, db: DB) -> ActivationOut:
    return service.activation_out(service.deactivate(ctx, db, obj, body))


@router.post("/activations/{activation_id}/health-check", response_model=HealthOut)
def health_check(obj: ActivationDep, ctx: Ctx, db: DB) -> HealthOut:
    return HealthOut.model_validate(asdict(service.health_check(ctx, db, obj)))
