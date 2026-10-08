# Common screens

Shared information used by every module, under **Common** in the left menu.

## Engagements

An engagement is a piece of work with the customer. DiscoveryQ sessions, FlowDesk flows, DevTracker projects and more belong to an engagement.

1. Enter name, description and status (preparing / in progress / on hold / completed) and click **Create**.
2. Select it in the engagement selector at the top to scope screens to it.

## System registry

The customer's information systems (MES, ERP, LIMS, WMS, SCADA, groupware, other) with name, short name, type, owning department, hosting (on-premise / cloud), DB type and notes. I/F source and target systems and FlowDesk node systems refer to these entries.

> A system that other data refers to cannot be deleted ("It is referenced by other data").

## Files

Keep material received from the customer. Upload with **Upload file**, then download or delete from the list. Allowed types are pdf, images (png/jpg/gif), txt, md, csv, json, Excel (xlsx/xlsm/xls), docx, pptx, zip and log, up to 20 MB by default.

## Asset library

Assets LUDA reuses across customers: question banks, process templates, I/F templates, upper ontologies, glossary templates, document templates, rule packs and agent templates. They are stored apart from customer data, which refers to them only by version.

- Everyone can view assets; only LUDA admins edit them.
- **New version** stores the content (JSON) with a change note. Status moves from draft to published to deprecated; published versions cannot be changed.
- **Compare versions** shows prompt and content changes side by side.
- **Export package / Import package** exchanges assets with another installation.

## Audit log

Visible to LUDA admins, FDEs and customer admins. It records who (actor), when, and what (action, target), append-only; entries cannot be edited or deleted. Creates, updates, deletes, exports and integration requests, approvals and calls are all logged. **Export CSV** downloads it.
