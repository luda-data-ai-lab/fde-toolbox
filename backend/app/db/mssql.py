"""SQL Server compatibility.

- ``String``/``Text`` are emitted as ``NVARCHAR`` and bound as ``SQL_WVARCHAR`` so Korean text
  survives any database collation.
- SQL Server rejects foreign keys that form multiple cascade paths (error 1785), so ``ON DELETE``
  actions are dropped from the DDL and applied here, before the ORM deletes a row.
"""

import re
from typing import Any

from sqlalchemy import ForeignKeyConstraint, Select, String, Table, Text, delete, event, inspect, select, update
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc
from sqlalchemy.engine.interfaces import ExecutionContext
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.sql.compiler import DDLCompiler, TypeCompiler

from app.db.base import Base

_ON_DELETE = re.compile(r" ON DELETE (CASCADE|SET NULL|SET DEFAULT|RESTRICT|NO ACTION)")


@compiles(String, "mssql")
def _string(element: String, compiler: TypeCompiler, **kw: Any) -> str:
    return compiler.process(NVARCHAR(element.length), **kw)


@compiles(Text, "mssql")
def _text(_element: Text, compiler: TypeCompiler, **kw: Any) -> str:
    return compiler.process(NVARCHAR(), **kw)


@compiles(ForeignKeyConstraint, "mssql")
def _foreign_key(element: ForeignKeyConstraint, compiler: DDLCompiler, **kw: Any) -> str:
    return _ON_DELETE.sub("", compiler.visit_foreign_key_constraint(element, **kw))


@event.listens_for(MSDialect_pyodbc, "do_setinputsizes")
def _unicode_binds(inputsizes: dict[Any, Any], _cursor: Any, _stmt: str, _params: Any, ctx: ExecutionContext) -> None:
    dbapi = ctx.dialect.loaded_dbapi
    for key, kind in list(inputsizes.items()):
        if kind == dbapi.SQL_VARCHAR:
            inputsizes[key] = dbapi.SQL_WVARCHAR
        elif kind == (dbapi.SQL_VARCHAR, 0, 0):
            inputsizes[key] = (dbapi.SQL_WVARCHAR, 0, 0)


def _referencing(table: Table) -> list[tuple[Table, str, str]]:
    refs = []
    for child in reversed(Base.metadata.sorted_tables):
        for fk in child.foreign_keys:
            if fk.column.table is table and fk.ondelete in ("CASCADE", "SET NULL"):
                refs.append((child, fk.parent.name, fk.ondelete))
    return refs


def emulate_on_delete(conn: Any, table: Table, ids: Select[Any]) -> None:
    """Apply the ON DELETE actions declared in the metadata for rows of ``table`` selected by ``ids``."""
    for child, column, action in _referencing(table):
        col = child.c[column]
        if action == "SET NULL":
            conn.execute(update(child).where(col.in_(ids)).values({column: None}))
        else:
            if child is not table:
                emulate_on_delete(conn, child, select(child.c.id).where(col.in_(ids)))
            conn.execute(delete(child).where(col.in_(ids)))


@event.listens_for(Session, "before_flush")
def _before_flush(session: Session, _ctx: Any, _instances: Any) -> None:
    if not session.deleted or session.get_bind().dialect.name != "mssql":
        return
    conn = session.connection()
    for obj in list(session.deleted):
        table = inspect(obj).mapper.local_table
        if isinstance(table, Table) and "id" in table.c:
            emulate_on_delete(conn, table, select(table.c.id).where(table.c.id == obj.id))
