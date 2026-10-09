# DevTracker

DevTracker tracks development projects and tasks in the build stage. Pause notes and a log of prompts used with AI tools keep the context intact when someone else picks up the work.

## Creating a project

1. In **DevTracker**, enter name, engagement, tech stack, description and status (planning / active / on hold / done), then click **Create**.
2. Click a project in the list to open it.

## Project dashboard

The top of the project page shows total tasks, progress, overdue tasks (open tasks past their due date) and recent prompts.

## Tasks

- **Add task** with a title, priority (low / medium / high / urgent) and due date.
- The **Kanban** view shows a column per status (to do / in progress / review / done / on hold); the **List** view shows a table. Within a column, higher priority comes first.
- Click a task to change its status, priority and due date.

## Pausing and resuming

1. When you stop, open the task, write in the **Pause note** how far you got and what comes next, and click **Pause**. The task goes on hold.
2. When you restart, leave a **Resume note** and click **Resume**. This is only available for tasks on hold.

"Paused tasks" on the home screen lists everything that is on hold.

## Prompt log

Use **Log prompt** to record the tool used (Devin, Claude, etc.), the prompt and a summary of the result, for reference the next time.

## Creating a project from a SpecForge document

**Send to DevTracker** on a confirmed SpecForge document prefills the project form with the document title and engagement. After **Create**, the project opens and **Linked SpecForge documents** links back to the document. Only confirmed documents of the same customer and engagement can be linked.

## Issues

Record bugs, improvements and questions under **Issues** at the bottom of a project.

1. Enter title, type, priority and description, then click **Add issue**.
2. Change the status (open / in progress / resolved / closed) directly in the list.
3. Arriving from **Send to DevTracker issue** on an AgentHub deployment prefills the title with the instance name and records the source as "AgentHub".

Client users can only view issues.
