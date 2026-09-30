from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Table

from app.db.base import Base


def _encode(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def row_to_json(table: Table, values: dict[str, Any]) -> dict[str, Any]:
    return {c.name: _encode(values.get(c.name)) for c in table.columns}


def row_from_json(table: Table, values: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in table.columns:
        if col.name not in values:
            continue
        value = values[col.name]
        if isinstance(value, str) and isinstance(col.type, DateTime):
            value = datetime.fromisoformat(value)
        elif isinstance(value, str) and isinstance(col.type, Date):
            value = date.fromisoformat(value)
        out[col.name] = value
    return out


def table_of(model: type[Base]) -> Table:
    table = model.__table__
    assert isinstance(table, Table)
    return table
