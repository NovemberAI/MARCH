# 06. Tools and approvals

## Reuse before adding integrations

Reuse NovemberAI's existing intent compiler, schema validation, deterministic action classification, cancellation and approval machinery. Adapt its validated output into these capabilities; do not add a competing intent parser. Exact source paths must be discovered in the local checkout and recorded in `NOVEMBER-REUSE-MAP.md` during the first 15 minutes. The conceptual contracts below do not mandate renaming existing APIs.

Use as many ready-made products as reduce net implementation time, but one owner per responsibility. [Partner products](14-PARTNER-PRODUCTS.md) assigns each a role. A managed service does not replace tenant checks or action authorization.

## Capability registry

Expose typed capabilities with server-owned account routing:

- `calendar.list_events(start, end)`: read only that employee's enabled calendar within a bounded range.
- `calendar.find_slots(start, end, durationMinutes)`: deterministic free-slot calculation using read results, timezone and applicable preferences.
- `calendar.prepare_event(title, start, end, attendees)`: prepare a proposal, not create a Google event.
- `mail.search(query, maxResults)`: bounded employee-only query; no arbitrary account parameter.
- `mail.read(messageId)`: verify message belongs to current scope before returning content.
- `mail.prepare(to, subject, body)`: persist a pending proposal for owner review.
- `memory.propose(items)`: validated evidence-linked candidates, never permission changes.

`mail.send` is not a model-callable tool. It is a private dispatcher operation following valid approval. Calendar writes are disabled by default. Browser automation is not a wildcard capability.

If existing NovemberAI tool names differ, use an adapter instead of breaking its callers. Preserve negative instructions such as 'draft but do not send' as machine-readable constraints all the way to the dispatcher.

## Fixture adapters

Implement the registry first against employee-scoped MongoDB `fixture_items`. The fixture provider must exercise the same ownership and approval checks as live providers. An approved fake send inserts one simulated-send record and returns a fixture receipt. It is displayed as **simulated**, never as delivered email.

A complete sandbox prototype is an end-to-end working product with synthetic tools, not a fully connected real-office deployment. The status page and demo must distinguish these claims. If live authorization is unavailable, report 'live account integration blocked', not 'fully functional live integration'.

## Google connectors

Use separate OAuth grants and token records for each employee. The server supplies the connection; the model never chooses or sees it.

Initial scopes:

- `calendar.events.readonly` for reading event details, or a free/busy scope if details are unnecessary.
- `gmail.readonly` only if inbox reading is needed and approved.
- `gmail.send` only for separately enabled owner-approved sending.

Compose in MARCH first. Persisting Gmail drafts would need broader draft-management access, so it is not required for this prototype. Gmail `readonly` is a restricted scope and consent/organization policy can block setup. Three test accounts do not automatically bypass provider verification or administrative restrictions.

Do not use `https://mail.google.com/`, broad `calendar`, or deletion-capable calendar write scopes by default. Calendar event proposals can be copied or exported for manual creation. Actual creation is a separate explicitly authorized integration, not something to label completed because an `.ics` file exists.

Sources: [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth?hl=en).

## Exact-action approval protocol

1. Normalize a proposed payload and resolve the sender connection server-side.
2. Record payloadHash over canonical bytes plus actionType, owner, connectionId and mode.
3. Persist state=pending, expiry, source run and relevant memoryEpoch.
4. Present the complete payload and account identity. Show timezone on every event.
5. Owner explicitly approves on an authenticated personal surface for live mode. Demo mode uses visibly fictional identities.
6. Server checks principal ownership, unchanged payload/hash, unexpired approval, current permissions, connection readiness, and applicable constraints.
7. Atomically claim pending -> executing with a unique executionAttemptId.
8. Execute once, persist provider receipt and resulting state.
9. Read back/verify the result where the provider supports it. Do not trust the model's completion text.

Any edit to recipients, body, subject, date, attendee list or connection invalidates the approval. A second employee cannot approve or inherit the action. A quoted 'yes' in a message cannot approve it. Spoken affirmation alone is insufficient for live access on a shared desk.

For this user's own operation, keep the existing explicit post-preview approval convention; never treat the initial 'email them' command as send approval.

## Retry and duplicate prevention

Use a unique scoped idempotencyKey for the local action and atomic claims. This prevents duplicate dispatch inside MARCH, but it does not establish exactly-once delivery across a provider/network boundary.

If a send request times out after possible provider acceptance, mark `outcome_unknown`. Do not auto-retry and risk duplicate mail. Reconcile through an authorized provider read or require a human check. Do not silently acquire a broader scope solely to reconcile. Read-only calls may retry twice with bounded backoff; authentication and authorization failures do not retry with another account.

## Aside MCP integration gate

Official docs verify `aside mcp` exists. They do not establish the exact externally exposed tool list, persistent employee browser-profile isolation or safe concurrency for this application. Earlier planning is not implementation evidence.

Before enabling an Aside adapter:

1. Inspect NovemberAI's existing adapter and reuse it if available.
2. Perform a read-only MCP initialization/tools-list probe using the installed SDK.
3. Record actual schemas; do not expose internal Aside tools merely because another environment exposes them.
4. Test two controlled synthetic accounts/contexts for cookie, tab, download, history and memory separation.
5. Verify an action can target a stable employee-bound context, and that concurrent calls do not share a composer or mutable active tab.
6. Keep the deterministic approval broker in front of consequential actions.

Separate agent sessions are not sufficient proof. Incognito alone is not proof of three persistent isolated identities. Until the gate passes, keep Aside disabled for multi-employee private execution. It may be demonstrated separately on public pages or a single authorized operator context, accurately labeled.

Official starting point: https://docs.aside.com/help/developers

## Provider privacy

- Raindrop receives redacted traces/metrics by default, not raw microphone audio, tokens or complete inbox content.
- ElevenLabs receives only approved generic TTS text unless an employee explicitly permits private speech output.
- Modelence hosts the web/control plane where compatible, not an unverified copy of local biometric processing.
- MongoDB remains the canonical store for action state and harness promotion even if other products display traces.

Timeouts, permission failures and product outages must produce explicit application states without changing identity or bypassing approval.
