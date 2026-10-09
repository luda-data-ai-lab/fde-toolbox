# OntoMap glossary

Standardize the customer's business terms and keep the names each department uses for them, plus abbreviations.

## Tabs

| Tab | Contents |
| --- | --- |
| Glossary | Standard terms, create/edit, Excel/CSV export |
| Concept model | Edit concepts, attributes and relations; upper-ontology inheritance |
| Candidates | Term candidates raised from DiscoveryQ interviews |
| Validation | Warnings for the concept model and glossary |
| Excel import | Upload the LUDA glossary template |

## Adding a term

1. On **Glossary**, click **New term**.
2. Enter the standard term, definition, abbreviation, status (candidate / confirmed / deprecated) and notes.
3. Write **department aliases** as `Department: alias; alias`, for example `Production: recipe; BOM`.
4. Click **Save**. A term that already exists cannot be added again; merge into it instead.

## Concept model

The **Concept model** tab captures the customer's business concepts (for example production lot, work order), their attributes, and the relations between them.

1. In the form at the top, enter the **Concept name**, definition, owner department and status (draft/confirmed/deprecated), pick a **Parent concept**, then click **Add concept**.
   - The parent is either a LUDA upper-ontology concept (for example "로트" in the manufacturing common ontology) or a customer concept you already added.
   - Upper ontologies are LUDA assets shared by every customer. Concepts created here are stored for this customer only and never written to the asset.
2. Click a concept in the list to open its details. The inheritance path (for example `semi-finished lot → production lot → 로트 (manufacturing common v1)`) is shown at the top.
3. **Attributes**: enter the attribute name, data type, unit and whether it is required, then click **Add attribute**. Use **Set as identifier** for the attribute that identifies the concept. Attributes inherited from parents are greyed out with "Inherited: …".
4. **Relations**: enter the relation name, target concept, cardinality (1:1, 1:N, N:M) and inverse name, then click **Add relation**. Relations defined in the upper ontology are shown greyed out as well.
5. Use **Change parent** and **Change status** to edit in place. A change that would make inheritance circular (A → B → A) is rejected.
6. Terms linked to a concept appear under **Linked terms**.

## Validation

The **Validation** tab lists these warnings. Warnings never block saving.

- Concepts without a parent
- Concepts with the same name
- Confirmed terms without a definition
- Inherited upper-ontology concepts that can't be found

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
