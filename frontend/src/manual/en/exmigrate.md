# ExMigrate

ExMigrate analyzes the structure and formulas of a customer's Excel workbook, drafts an ERD (table design) from it, and turns the confirmed ERD into a DDL script and a data load script. Open it from **Analyze › ExMigrate (Excel)** in the sidebar.

- Macro-enabled `.xlsm` files can be read, but macros are **never executed**.
- FDE Toolbox never loads data into an external database. You download the scripts and run them in the customer's environment.
- Uploaded files and analyses are stored per customer, and uploads, confirmations and exports are recorded in the audit log.

## Uploading a workbook

1. Select a customer at the top and an **engagement** on the screen.
2. Choose an Excel file (`.xlsx`, `.xlsm`) and click **Upload and analyze**.
3. The detail view opens when the analysis is done. The list shows the file name, number of sheets, number of formulas and the ERD state (Draft / Confirmed).

## Structure

Each sheet shows its range, the estimated header row, the number of data rows, and per-column details.

| Item | Meaning |
| --- | --- |
| Type | Type inferred from the values (integer, decimal, boolean, date, date-time, text) |
| Empty % | Share of data rows where the cell is empty |
| Distinct | Number of different values |
| Formula cells | Number of cells in the column that contain a formula |
| Samples | Up to three example values |

**Quality warnings** list merged cells, blank rows inside the data, columns without a header, duplicate headers, columns with mixed types, empty sheets and references to external workbooks. Use them to find what to clean up in the source before migrating.

## Formulas

- Stage 1: where formulas are and how many (the first 50 cells per sheet are listed).
- Stage 2: how often simple functions such as SUM, IF, VLOOKUP and INDEX/MATCH are used, and how many formulas reference other sheets.
- Complex formulas such as LAMBDA or LET are only counted, not interpreted.

## Editing and confirming the ERD

The **ERD** tab drafts one table per sheet. Column names are turned into database-safe names and the original header is kept under "Original name". Columns such as `id`, `code` or `no` that have no empty values and no duplicates are marked as primary-key candidates. Formulas that look up another sheet with VLOOKUP, XLOOKUP or MATCH become relation candidates (child column → parent column).

1. Edit table names, column names, types, PK and Nullable. Drop tables or columns you don't need.
2. Use **Add relation** to add a relation by hand, or remove wrong ones.
3. Click **Save ERD**. Duplicate names, invalid names and relations pointing at missing columns are listed under "Fix before confirming".
4. When nothing is left to fix, click **Confirm ERD**. Saving changes after confirming unconfirms the ERD, so confirm it again.

## Generating scripts

Once the ERD is confirmed, the **Scripts** tab lets you pick a target database (PostgreSQL, SQL Server, SQLite) and preview the DDL. **Download scripts ZIP** gives you:

| File | Contents |
| --- | --- |
| `schema.sql` | DDL creating the tables, primary keys and foreign keys |
| `load.py` | Python script that reads the workbook and inserts the rows (parent tables first) |
| `mapping.json` | Mapping between sheets/columns and tables/columns |
| `README.md` | How to run it |

In the customer's environment run `schema.sql` first, then `load.py` (the packages each database needs and connection string examples are at the top of `load.py`).
```powershell
pip install openpyxl psycopg
python load.py source.xlsx --dialect postgresql --url "postgresql://user:pw@host/db"
```

## Exports

At the top of the detail view, download the **Analysis report (MD)** (structure, formulas and warnings) and the **ERD (Mermaid)**. Customer users (read-only) can view results but cannot upload, edit or confirm the ERD, or export.

## Sending to SpecForge

After the ERD is confirmed, **Send to SpecForge** appears on the ERD tab. It opens SpecForge's new-document form with this analysis's ERD selected. Tables, columns and relations of the confirmed ERD go into the "Domain concept model" section of Spec.md and the "Data model" section of Devin.md.
