# AgentHub

AgentHub is a registry for AI agents deployed to customers in the operate stage. It does not run agents; it records template versions, evaluation results and deployments.

## Agent templates

- **Agent templates** are reusable agent definitions stored in the LUDA asset library. Click one to see each version's system prompt and change note.
- Compare versions to see how the prompt changed. Templates are edited by LUDA admins in the [asset library](/manual/workspace).

## Evaluation cases and runs

1. Under **Evaluation cases** on the template page, add an input, expected result and pass criteria.
2. After trying the agent, use **Record evaluation** to store pass/fail per case.
3. Check the **Pass rate** per version in the evaluation results.

## Deployed instances

1. Under **Deployed instances**, enter a name, template and version, deployment type (standalone / LUDA hosted / customer environment), linked development project, connected systems and notes, then click **Create**.
2. Update the status (ready / pilot / production / stopped) as it changes. Home shows instance counts by status.

## Sending to a DevTracker issue

When a deployment is linked to a DevTracker project, **Send to DevTracker issue** appears in the list. It opens that project's issue form so you can record a problem found in operation, with this instance as its source. The instance and project must belong to the same engagement.
