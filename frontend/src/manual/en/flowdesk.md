# FlowDesk

FlowDesk is a canvas for drawing and editing business flows. Steps sit on swimlanes (horizontal bands per department or role) and are connected to each other, and each step can be linked to a system from the system registry. The current flow (As-Is) and the improved flow (To-Be) are kept as a pair.

## Creating a flow

1. Select a customer and an **engagement** at the top. You cannot create a flow without an engagement.
2. Under **New flow**, set the title, kind (As-Is / To-Be) and perspective (business / PM / developer / executive / consultant).
3. Choose a LUDA process **template** (for example "Paint order → production → shipping" or "Quality inspection and nonconformance") to lay out lanes and steps automatically, or **Blank canvas** to start from scratch.
4. Click **Create** to open the editor.

The list can be filtered by engagement and kind; flows with a counterpart show "Paired".

## Editing the canvas

| To | Do this |
| --- | --- |
| Add a step | Pick a type under **Add node** on the right and click **Add** |
| Move a step | Drag it; dropping it on a lane puts it in that lane |
| Connect steps | Drag from the dot on a node's right edge to another node |
| Change name, type or system | Click the node and edit it in the **Node** panel |
| Add a branch condition | Click the connection and enter a **Condition** |
| Delete | Select a node or connection and press Delete |
| Pan and zoom | Drag empty space, use the mouse wheel, or the zoom buttons at the bottom left |

Node types are start, end, task, decision, system, document, role and note. When you pick a **System**, its short name is shown on the node. Register missing systems in the [system registry](/manual/workspace) first.

In the **Swimlanes** panel, type a lane name and click **Add**, or **Delete** a lane. Nodes in a deleted lane stay on the canvas without a lane.

Click **Save** at the top after making changes. The button changes to "Saved".

## As-Is / To-Be pairs

- On an As-Is flow, **Create To-Be** copies the current graph into a new To-Be flow and opens it. A To-Be flow offers **Create As-Is** instead.
- Once paired, use **Open To-Be** / **Open As-Is** to switch.
- Deleting one flow removes the pairing from the other.

## Snapshots

Keep versions of the graph at important moments (right after an interview, before a customer review).

1. Save your changes first; you cannot take a snapshot with unsaved changes.
2. Enter a **Snapshot note** and click **Save snapshot**. Snapshots are numbered v1, v2, and so on.
3. **Restore** returns the canvas to that version. Unsaved changes are lost.

## Export and import

| Button | Result |
| --- | --- |
| JSON | The whole flow (title, kind, perspective, graph) as JSON; can be imported into another customer or installation |
| Mermaid | Mermaid `flowchart` text (.mmd), lanes as subgraphs, with linked system names |
| SVG | Vector image that stays sharp in documents |
| PNG | Image file |

**Import JSON** on the list screen adds the selected file as a new flow in the current engagement. Links to another customer's systems are not imported.

> SVG/PNG images are made in the browser; JSON and Mermaid exports are recorded in the audit log. Nothing is sent outside.
