# 08. API and UI contracts

## Adapt to NovemberAI; do not replace it

The endpoints below are logical contracts for the MARCH wrapper. Implement them as existing NovemberAI modules/routes when possible, or as thin Modelence/Node handlers. Do not introduce a new Python service, ASR engine or intent compiler just to match these names. Keep the original runtime and lock files.

Browser requests must not gain authority by supplying employeeId. Demo fixture selection and device candidate events are explicitly mode-limited; live scope comes from authenticated server state.

## Minimal endpoints

### `GET /health`

Returns status, appVersion, mode and non-secret readiness booleans for Atlas, November bridge, model, voice profiles, vector index and optional integrations. No tokens, connection strings, emails or host filesystem paths.

### `POST /api/demo/select-profile`

Demo-only debug route. Input fixtureEmployeeId; verifies membership in the three seeded fictional IDs and creates a demo session binding. Disabled in live mode. UI labels it manual fixture identity. Not used during the claimed voice-recognition demonstration.

### `POST /api/enrollment/start`

Operator/owner-authenticated route. Input consent confirmation and intended fixture identity for demo; live identity is derived from the owner session. Returns enrollmentId and audio instructions. Does not accept uploaded credentials or authorize account access.

### `POST /api/enrollment/{id}/clips`

Audio upload or trusted November runtime reference. Validates session ownership, bounded decoded length and quality. Returns progress and reason codes. If November owns capture, reuse its audio buffers rather than record simultaneously in the web app.

### `POST /api/enrollment/{id}/finish`

Persists encrypted profile and held-back check result. Returns ready only after persistence. No voice embedding is returned to the browser.

### `POST /api/runs`

Input: sessionId, utteranceId, transcript or capture reference, and existing November compiled intent in the trusted bridge path. InputSource is `november_voice | november_text | manual_demo`. Retain original utterance and machine-readable negations.

A trusted local bridge may transport a candidate speaker and validated intent, but the server still resolves scope. Browser-supplied intent is revalidated and cannot override policy.

Returns runId and initial state. Long work uses polling; WebSockets are unnecessary for the first build.

### `GET /api/runs/{id}`

Owner-scoped response: state, recognized fixture label if allowed, transcript, result, selected memory references, pending action IDs and harness version. Shared unauthenticated display receives only generic state, never private bodies.

### `POST /api/runs/{id}/cancel`

Cancels pending work owned by the requester. Reports if an external action has already started and cannot be reliably recalled. Cancellation is not proof that a previously dispatched email was unsent.

### `GET /api/memories`

Scoped memory list with safe text, kind, source time and status; no embeddings or internal secrets.

### `POST /api/memories/{id}/correct`

Owner correction with value/text and validity. Updates canonical preference, history and epoch atomically where supported. Invalidates affected pending proposals.

### `DELETE /api/memories/{id}`

Owner-requested forgetting, not external mailbox deletion. Removes retrieval access immediately and queues/executes derived cleanup. Returns deletion status and whether physical cleanup remains pending. Never exposes another employee's existence through distinguishable error details.

### `POST /api/actions/{id}/approve`

Input displayedPayloadHash. Server derives principal and validates the exact action, scope, mode, connection, expiry and constraints. No `approved=true` field from a model is accepted. Returns executing or a specific safe rejection state.

### `POST /api/actions/{id}/reject`

Owner-scoped refusal, with optional correction. Rejecting one action does not approve a replacement.

### `POST /api/runs/{id}/feedback`

Input type and optional structured correction. Explicit user feedback is separate from untrusted text embedded inside emails/tool results.

### `POST /api/harness/improve`

Starts one bounded cycle for the current employee, subject to operator/owner capability and cost budget. Does not accept raw arbitrary code or an evaluator replacement. Returns candidateVersionId/job status.

### `GET /api/harness/evaluations/{id}`

Scoped/synthetic-safe summary: baseline/candidate versions, diff, suite, fixture hash, pass counts, critical failures, cost and decision. No invented progress percentages.

### `POST /api/harness/rollback`

Input targetVersionId; validates same employee and immutable known version. Operator/owner capability required; compare-and-set active pointer and log the transition.

## November local-to-cloud bridge

Preferred if existing voice/intent code is Python and Modelence hosts the Node app:

1. Keep capture, ASR and intent compilation in the existing local process.
2. Add a thin outbound HTTPS client that posts normalized November events to MARCH.
3. Register a short-lived device credential with the hosted app; keep it in the local secret store, never frontend JavaScript.
4. Sign or authenticate each event; include eventId, timestamp, nonce/counter and capture/session correlation. Reject replay and expired events.
5. Cloud server maps device/capture binding to allowed demo identities. Live owner authentication is still separate.
6. Return a response or run handle to the initiating local process; it can poll and invoke existing TTS.

The cloud service never calls laptop `localhost`. No public tunnel, port-forwarding or new incoming laptop listener is required. A publicly deployed browser must not be instructed to bypass browser security to reach a private microphone service.

If November is already Node/TypeScript, import its existing modules into the single service where feasible. If a bridge cannot be made quickly, keep the entire local prototype and use Atlas/other products directly; visibly mark hosted integration deferred.

## Typed errors

`UNKNOWN_SPEAKER`, `AMBIGUOUS_SPEAKER`, `INSUFFICIENT_AUDIO`, `DESK_BUSY`, `AUTH_REQUIRED`, `SCOPE_DENIED`, `CONNECTOR_UNAVAILABLE`, `APPROVAL_REQUIRED`, `APPROVAL_EXPIRED`, `PAYLOAD_CHANGED`, `OUTCOME_UNKNOWN`, `PERSISTENCE_UNAVAILABLE`, `VECTOR_FALLBACK`, `BUDGET_EXHAUSTED`, `CANDIDATE_REJECTED`.

Use consistent HTTP status codes and correlation IDs. Return generic not-found/denied responses for inaccessible resource IDs. Never include provider secrets or stack traces in public errors.

## UI surfaces

### Desk

One clear microphone control or connection indicator for the existing November capture UI. Show listening/transcribing/identifying/thinking/awaiting-approval/result states. Display matched fictional employee and input provenance. Persistent demo/live badge. No dashboard as the main product.

### Personal workspace

Own short conversation, memory list, pending actions, and connector status. In live mode this belongs on an authenticated personal surface. A shared kiosk must not expose another employee's results after switching speakers.

### Action preview

Sender/account, complete recipient list, subject/body or event details/timezone, explicit approve/reject, and expiry. Changed content clears prior approval.

### Improvement evidence drawer

Old/new configuration diff, real run IDs, pass counts and denominators, critical-test status, token/latency observations and promoted/rejected status. Raindrop links are supplemental; MongoDB results remain sufficient if telemetry is offline.

### Operator setup

Three enrollment slots, consent/revoke controls, integration readiness and safe synthetic reseed. No secret values displayed. Destructive reset applies only to the named demo/eval database after explicit confirmation.

## Responsiveness and accessibility

Use existing November UI components if available. Otherwise build a minimal React surface. Provide keyboard capture/cancel controls, visible focus, clear errors and textual status rather than color alone. Keep private text out of automatic spoken responses. Latency targets are engineering goals to measure, not predeclared results.
