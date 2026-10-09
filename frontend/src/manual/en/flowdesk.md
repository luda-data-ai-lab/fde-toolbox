# FlowDesk

FlowDesk is a canvas for drawing and editing business flows. Steps sit on swimlanes (horizontal bands per department or role) and are connected to each other, and each step can be linked to a system from the system registry. The current flow (As-Is) and the improved flow (To-Be) are kept as a pair.

## Creating a flow

1. Select a customer and an **engagement** at the top. You cannot create a flow without an engagement.
2. Under **New flow**, set the title, kind (As-Is / To-Be) and perspective (business / PM / developer / executive / consultant).
3. Choose a LUDA process **template** (for example "Paint order → production → shipping" or "Quality inspection and nonconformance") to lay out lanes and steps automatically, or **Blank canvas** to start from scratch.
4. Click **Create** to open the editor.

The list can be filtered by engagement and kind; flows with a counterpart show "Paired".

## Generating a flow (prompt / LLM)

Draft a flow from a process description or DiscoveryQ interview insights. After you pick an engagement, the list screen shows a **Generate a flow (prompt / LLM)** section.

1. Set the title, kind (As-Is/To-Be) and perspective. The prompt changes with the perspective.
   - Business: departments, documents, manual and waiting steps in detail (12-25 steps)
   - PM: owners, deliverables, approvals and bottlenecks (10-20 steps)
   - Developer: the system behind each step, data and interface points between systems, exception branches (15-30 steps)
   - Executive: only key stages and decisions (5-10 steps)
   - Consultant: note nodes that point out problems (As-Is) or improvements (To-Be) (10-20 steps)
2. Write a **Process description** or pick one or more **DiscoveryQ insights**. At least one of them is required.
3. Click **Build prompt**. The prompt contains your inputs, the names in the tenant's system registry and the expected JSON format.
4. There are two ways to get the result.
   - **Prompt-copy mode** (default): click **Copy prompt**, paste it into an LLM your organisation allows, paste the returned JSON into **Paste LLM result** and click **Create flow from result**.
   - **Generate with LLM**: shown only when the LLM adapter is approved and active under [External integrations](/manual/adapters). It sends the same prompt through the LLM adapter, and the call is recorded in the audit log.
5. A new flow is created and opens in the editor. Lanes come from the departments or roles in the result, and nodes are laid out left to right in connection order.

FlowDesk cleans up the result when it builds the flow.
- Unknown node types become **Task**; duplicate nodes and connections to missing nodes are dropped.
- A node's system name is linked to the registry system with the same name or short name (case-insensitive).
- If the answer isn't JSON or doesn't match the format, you get "Couldn't turn the LLM result into a flow" and no flow is created.

> In prompt-copy mode FDE Toolbox makes no external calls. The copied prompt contains your description, the selected insights and system names, so paste it only into an LLM the customer allows.

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

## Sending to SpecForge

On a saved flow, **Send to SpecForge** at the top of the canvas opens SpecForge's new-document form with this flow selected. The button is hidden while there are unsaved changes, so save first. When you arrive from a DiscoveryQ session via **Send to FlowDesk**, that session's insights are preselected in flow generation.
