from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class AssetRef(BaseModel):
    asset_id: str
    version: int


def dump_patch(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True)
