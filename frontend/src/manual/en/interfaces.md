# I/F management

Collect the customer's system-to-system interfaces (I/Fs) from Excel, and review per-system traffic and a connection graph.

## Tabs

| Tab | Contents |
| --- | --- |
| List | Search, filter, create, edit and delete I/Fs |
| Excel upload | Upload, validate and apply the LUDA I/F template |
| Dashboard | Total I/Fs, outgoing/incoming counts per system, status and link-type breakdown |
| Connection graph | Systems as nodes, I/Fs as arrows |

## Bulk import from Excel

1. Click **Excel template** to download the LUDA I/F template. It has an interface list sheet and a system connection sheet.
2. Fill it in with the customer's data. Key columns: I/F ID, I/F name, source system, target system, link type (DB Link / API / File / MQ / EAI / Other), schedule, data items, daily volume, owner and status (planned / developing / operating / retired).
3. Choose the file on **Excel upload**. Each row shows its validation result (new / update / error) and any problems.
4. Systems missing from the system registry are listed as "Unregistered systems". Tick the ones to register; they are created when you apply. Rows that reference unticked systems are skipped.
5. Click **Apply**. A summary shows how many rows were created, updated and skipped and how many systems were registered. An existing I/F ID is updated.

> Error rows (missing required values, unknown link type or status, non-numeric volume, duplicates in the file) are not applied. Fix the workbook and upload it again.

## Managing the list

On **List**, filter by system, status and link type, or search. FDEs and LUDA admins can create, edit and delete rows.

## Dashboard and graph

- **Dashboard**: find systems with the most connections from the outgoing/incoming counts.
- **Connection graph**: see how systems connect. **Save PNG** downloads the picture for reports.

## Exports

**Export Excel** and **Export CSV** download the current list. Cell values are escaped so they cannot run as formulas.
