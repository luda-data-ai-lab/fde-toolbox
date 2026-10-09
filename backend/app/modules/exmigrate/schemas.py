from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

ColumnType = Literal["integer", "decimal", "boolean", "date", "datetime", "text"]
Dialect = Literal["sqlite", "postgresql", "mssql"]
RelationOrigin = Literal["formula", "name", "manual"]

MAX_TABLES = 200
MAX_COLUMNS = 500


class ColumnReport(BaseModel):
    letter: str
    name: str
    inferred_type: ColumnType | None
    null_ratio: float
    distinct: int
    samples: list[str] = Field(default_factory=list)
    formula_cells: int = 0


class SheetWarning(BaseModel):
    code: str
    where: str | None = None
    detail: str | None = None


class FunctionUse(BaseModel):
    name: str
    count: int
    simple: bool


class SheetRef(BaseModel):
    sheet: str
    count: int


class FormulaCell(BaseModel):
    cell: str
    formula: str


class LookupRef(BaseModel):
    column: str
    target_sheet: str
    target_column: str
    count: int


class FormulaSummary(BaseModel):
    count: int = 0
    complex: int = 0
    cells: list[FormulaCell] = Field(default_factory=list)
    functions: list[FunctionUse] = Field(default_factory=list)
    references: list[SheetRef] = Field(default_factory=list)
    lookups: list[LookupRef] = Field(default_factory=list)


class SheetReport(BaseModel):
    name: str
    dimension: str
    max_row: int
    max_column: int
    header_row: int | None
    data_rows: int
    columns: list[ColumnReport] = Field(default_factory=list)
    warnings: list[SheetWarning] = Field(default_factory=list)
    formulas: FormulaSummary = Field(default_factory=FormulaSummary)


class WorkbookReport(BaseModel):
    sheets: list[SheetReport] = Field(default_factory=list)
    has_macros: bool = False
    formula_count: int = 0
    complex_formulas: int = 0
    functions: list[FunctionUse] = Field(default_factory=list)


class ErdColumn(BaseModel):
    name: str = Field(min_length=1, max_length=63)
    label: str = Field(default="", max_length=300)
    type: ColumnType = "text"
    nullable: bool = True
    primary_key: bool = False
    source_column: str | None = Field(default=None, max_length=3)


class ErdTable(BaseModel):
    name: str = Field(min_length=1, max_length=63)
    label: str = Field(default="", max_length=300)
    source_sheet: str | None = Field(default=None, max_length=300)
    header_row: int | None = Field(default=None, ge=1)
    columns: list[ErdColumn] = Field(min_length=1, max_length=MAX_COLUMNS)


class ErdRelation(BaseModel):
    from_table: str = Field(min_length=1, max_length=63)
    from_column: str = Field(min_length=1, max_length=63)
    to_table: str = Field(min_length=1, max_length=63)
    to_column: str = Field(min_length=1, max_length=63)
    origin: RelationOrigin = "manual"


class Erd(BaseModel):
    tables: list[ErdTable] = Field(default_factory=list, max_length=MAX_TABLES)
    relations: list[ErdRelation] = Field(default_factory=list, max_length=MAX_TABLES * 10)


class ErdOut(ORMModel):
    id: str
    analysis_id: str
    erd: Erd
    confirmed: bool
    confirmed_at: datetime | None
    issues: list[str] = Field(default_factory=list)


class AnalysisSummary(ORMModel):
    id: str
    engagement_id: str
    file_id: str
    filename: str
    status: str
    created_at: datetime
    sheets: int = 0
    formula_count: int = 0
    erd_confirmed: bool = False


class AnalysisOut(AnalysisSummary):
    report: WorkbookReport
