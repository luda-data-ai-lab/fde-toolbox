# External integrations (adapters)

Features that send data to outside services such as an LLM work only through adapters. External integrations are off in a default installation, and this menu is hidden.

## When the menu appears

**Common › External integrations** appears when the server `.env` sets `ADAPTERS_ALLOWED=true` and you are a LUDA admin, FDE or customer admin.

## Activation steps

1. An **FDE** reviews the adapter's **data egress scope** (destination, data sent, features), enters settings such as model, max tokens, timeout and API key, and clicks **Request activation**. The status becomes "Pending approval".
2. A **customer admin** reviews the scope, ticks the acknowledgement, and clicks **Approve**, or **Reject** if it is not acceptable.
3. In a standalone installation with no customer admin, a LUDA admin approves and must enter an **approval reason**.
4. Once active, **Check connection** tests the outside service.
5. **Deactivate** it when it is no longer needed. Rejecting or deactivating deletes the stored credentials.

## Security

- API keys are entered on this screen, not in `.env`, and stored encrypted. They never appear on screen, in the audit log or in customer ZIP exports.
- A customer imported from a ZIP therefore has no credentials and needs its activation requested again.
- Each outside call records the feature, request/response size, result and duration in the audit log. Content is not stored.

## When integrations are off

Without an active adapter, features that would call outside run in "prompt copy mode": copy the prompt the screen builds into an approved tool yourself, then paste the result back.
