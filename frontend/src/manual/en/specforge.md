# SpecForge

Builds the **Spec.md** and **Devin.md** you hand to an AI coding agent (Devin and others) from your engagement's outputs. It fills the sections of a LUDA document template with DiscoveryQ insights, FlowDesk flows, the I/F list, the OntoMap glossary and free-form requirements using fixed rules (no LLM), then lets you edit, save versions, compare and download.

## Assembling a document

1. Pick the tenant and **engagement** at the top. You cannot create a document without an engagement.
2. Under **Assemble a new document**, choose the **Document type** (Spec.md/Devin.md) and a title. Pick a **Template** from the LUDA templates for that type.
3. Pick **Rule packs**. Their rules are copied into the "Work rules" section of Devin.md.
4. Under **Inputs**, choose what to include.
   - DiscoveryQ sessions: summaries and insights go to "Feature specification"; action items go to the Devin.md "Steps" section.
   - FlowDesk flows: lanes, main steps and related systems go to "Overall structure".
   - I/F list: the tenant's interfaces as a table in "Overall structure".
   - OntoMap glossary: confirmed terms and department aliases as a table in Spec.md "Terms"; Devin.md "Data model" gets the instruction that the data model follows these terms, plus the term table.
5. Optionally enter **Free-form requirements**. They go to "Overview" (Devin.md: "Goal").
6. Click **Assemble draft** to open the editor.

Sections without input keep the template's writing rule as `> TODO: …`. Only outputs of the same engagement can be selected.

## Editing and preview

Edit in the **Markdown editor** on the left; the **Preview** on the right updates as you type. Click **Save** at the top to store your changes; until then "You have unsaved changes." is shown.

**Re-assemble** rebuilds the draft from the selected inputs (picking up new insights and terms). It replaces your edits, so save a version first.

## Versions and comparison

- **Save version** stores the saved content as v1, v2 … with an optional note.
- **Restore** puts a version's content back into the document.
- **Compare from / Compare to** shows a line diff between two versions, or a version and the **Current working copy** (green added, red removed).

## Enrich (LLM or prompt copy)

**Build prompt** creates a prompt asking to polish the current document. It tells the model to keep the section structure and work rules and not to invent anything the document does not mention.

- With the LLM adapter off (default): **Copy** the prompt, run it in an approved external tool, paste the answer into **Paste result** and click **Apply to editor**.
- With the LLM adapter approved and active, an **Enrich with LLM** button appears. The result lands in the editor as an unsaved change; review it, then **Save**. Calls are audit-logged. See [External adapters](/manual/adapters) for setup.

## Confirming and exporting

- **Confirm** sets the status to "Confirmed". Click **Back to draft** to edit again.
- **Download Spec.md / Download Devin.md** downloads one document.
- **Export ZIP** on the list downloads all documents of the selected engagement (or the whole tenant) in one ZIP. Duplicates are numbered, e.g. `Spec-2.md`.

## Permissions

| Role | Allowed |
| --- | --- |
| LUDA admin, FDE | Assemble, edit, versions, enrich, confirm, delete, export |
| Client admin | View, export |
| Client user | View |

Every create, update, version, restore, enrich and export is recorded in the [audit log](/manual/workspace).
