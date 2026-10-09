# OntoMap glossary

Standardize the customer's business terms and keep the names each department uses for them, plus abbreviations.

## Tabs

| Tab | Contents |
| --- | --- |
| Glossary | Standard terms, create/edit, Excel/CSV export |
| Candidates | Term candidates raised from DiscoveryQ interviews |
| Excel import | Upload the LUDA glossary template |

## Adding a term

1. On **Glossary**, click **New term**.
2. Enter the standard term, definition, abbreviation, status (candidate / confirmed / deprecated) and notes.
3. Write **department aliases** as `Department: alias; alias`, for example `Production: recipe; BOM`.
4. Click **Save**. A term that already exists cannot be added again; merge into it instead.

## Reviewing candidates from interviews

Phrases registered from a [DiscoveryQ](/manual/discoveryq) worksheet appear on **Candidates** as "Pending review", with their source session, department and similar existing terms.

- **Confirm**: adds it to the glossary as a new standard term.
- **Merge into {term}**: adds it as a department alias of a similar existing term.
- **Ignore**: keeps it out of the glossary. **Reopen** undoes this.

## Importing from Excel

1. On **Excel import**, choose an .xlsx file in the LUDA glossary template format.
2. Each row shows new / update / skip and any errors.
3. When applied, existing terms are updated and aliases are added to the existing ones.

## Exports

**Export Excel** produces the template format, which can be imported again. **Export CSV** has standard term, definition, department aliases, abbreviation, related concepts, notes and status columns.

## Sending to SpecForge

**Send to SpecForge** at the top opens SpecForge's new-document form with the "OntoMap glossary" input selected.
