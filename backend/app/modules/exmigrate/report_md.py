"""Analysis report as Markdown (pure)."""

from app.modules.exmigrate.schemas import WorkbookReport


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_markdown(report: WorkbookReport, filename: str) -> str:
    out = [f"# ExMigrate analysis: {_cell(filename)}", ""]
    out += [
        f"- Sheets: {len(report.sheets)}",
        f"- Formulas: {report.formula_count} (complex: {report.complex_formulas})",
        f"- Macros present (not executed): {'yes' if report.has_macros else 'no'}",
        "",
    ]
    if report.functions:
        out += ["## Functions", "", "| Function | Formulas | Simple |", "|---|---|---|"]
        out += [f"| {f.name} | {f.count} | {'yes' if f.simple else 'no'} |" for f in report.functions]
        out.append("")
    for s in report.sheets:
        out += [f"## Sheet: {_cell(s.name)}", ""]
        out += [f"- Range: {s.dimension}, header row: {s.header_row or '-'}, data rows: {s.data_rows}", ""]
        if s.columns:
            out += [
                "| Column | Name | Type | Null % | Distinct | Formulas | Samples |",
                "|---|---|---|---|---|---|---|",
            ]
            out += [
                f"| {c.letter} | {_cell(c.name)} | {c.inferred_type or '-'} | {round(c.null_ratio * 100, 1)} | "
                f"{c.distinct} | {c.formula_cells} | {_cell(', '.join(c.samples))} |"
                for c in s.columns
            ]
            out.append("")
        if s.formulas.references:
            refs = ", ".join(f"{_cell(r.sheet)} ({r.count})" for r in s.formulas.references)
            out += [f"- Cross-sheet references: {refs}", ""]
        if s.warnings:
            out += ["### Warnings", ""]
            out += [
                f"- {w.code}"
                + (f" @ {_cell(w.where)}" if w.where else "")
                + (f": {_cell(w.detail)}" if w.detail else "")
                for w in s.warnings
            ]
            out.append("")
    return "\n".join(out).rstrip() + "\n"
