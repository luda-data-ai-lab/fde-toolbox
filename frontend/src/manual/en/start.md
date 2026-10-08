# Getting started

FDE Toolbox lets a forward-deployed engineer (FDE) carry a customer engagement through **diagnose → analyze → design → build → operate** in one place. All data is stored separately per customer (tenant), and by default nothing is sent outside the installation.

## Signing in

1. Sign in with the email and password your administrator gave you.
2. Your name and role appear at the top right. Click **Log out** when you are done.

## Screen layout

- **Left menu**: grouped by stage. Diagnose (DiscoveryQ), Analyze (I/F management, OntoMap glossary), Design (FlowDesk, SpecForge), Build (DevTracker), Operate (AgentHub), Common (engagements, system registry, files, asset library, audit log and more).
- **Customer selector** (top): the customer you are working on. Every screen shows only that customer's data.
- **Engagement selector** (top): narrows screens to one engagement. "All engagements" shows the whole customer.
- **Manual**: opens the manual page for the screen you are on.
- **English / 한국어**: switches the UI language; the manual follows.

## Roles and permissions

| Role | Can do |
| --- | --- |
| LUDA admin | View and edit every customer, manage customers and users, edit the asset library, ZIP export/import |
| FDE | View, create, edit and delete in assigned customers; export; view the audit log |
| Customer admin | View own company data, export, view the audit log, approve external integrations |
| Customer user | View own company data |

Screens you cannot use show "Permission denied", and edit buttons are hidden.

## Home

Home shows a summary for your role. LUDA admins see customer, user and asset counts; FDEs and customer users see open and paused tasks and agent instance status. **Switch to customer** on a customer card changes the customer selector.

## Typical flow

1. In the [common screens](/manual/workspace), create an engagement and register the customer's systems.
2. Record field interviews with [DiscoveryQ](/manual/discoveryq).
3. Organize system interfaces and terms with [I/F management](/manual/interfaces) and [OntoMap](/manual/ontomap).
4. Draw As-Is/To-Be business flows in [FlowDesk](/manual/flowdesk), then assemble Spec.md and Devin.md from your outputs in [SpecForge](/manual/specforge).
5. Track build work in [DevTracker](/manual/devtracker) and deployed agents in [AgentHub](/manual/agenthub).
