# 02. Architecture

## A small application, not a swarm

Reuse the existing NovemberAI process for capture, ASR, intent compilation and policy ([13](13-NOVEMBERAI-REUSE.md)). Add one MARCH web/control-plane service (Node/TS if hosted on Modelence; otherwise match NovemberAI's language) and MongoDB Atlas. Implement logical components as modules, not microservices. One bounded background task queue is enough. The model can reason about tasks, but deterministic code owns identity, data scope and execution authorization.

## Components and responsibilities

### Desk UI

Captures opt-in audio, displays capture/transcription/match state, shows synthetic demo output, and offers a compact history/improvement view. It cannot assert an authenticated employee by sending an ID. A profile selector is allowed only in visibly labeled text-demo/testing mode.

### Voice service

Converts supported audio to normalized mono PCM, rejects insufficient or ambiguous recordings, produces an embedding, compares against enrolled profiles and returns a candidate identity with scores. It does not read email/calendar data or grant authorization.

### Identity resolver

Creates the immutable `RequestScope` from server state. Demo mode may bind a recognized voice to fictional data. Live mode requires an independently authenticated owner session and checks any voice match against that owner. An untrusted shared kiosk is not a live personal-data display.

### Orchestrator

Loads a pinned harness version, assembles that employee's context, calls the task model, validates typed tool requests, and handles a bounded number of read calls. It creates proposals rather than executing external writes. A run's owner and harness version do not change midway through a speaker switch or policy promotion.

### Scoped repositories

Every method requires `RequestScope`. They add `orgId`, `employeeId` and mode checks; callers cannot override filters with query payloads. Vector search, direct lookup, linked notes, action IDs, caches and trace reads follow the same rule.

### Memory service

Converts permitted evidence into small notes, records source, handles correction/supersession/deletion, and provides context. Tool content is untrusted data and cannot create authorization rules.

### Tool broker

Maps typed capabilities to employee-bound fixture or live adapters. The model does not see OAuth secrets, choose `connectionId`, supply an arbitrary account, or call an unrestricted browser tool.

### Approval dispatcher

Owns pending action states and exact payload hashes. Only a valid owner approval can transition an action toward execution. The model cannot manufacture an approval or directly invoke the dispatcher.

### Improvement worker

Reads a tenant-scoped run/feedback bundle, proposes one allowlisted configuration patch, creates an immutable candidate, and evaluates it in the isolated fixture environment. It cannot access credentials or modify application files, evaluation answers or security code.

## Canonical data contracts

Define these as typed schemas in the MARCH service (Pydantic, Zod or equivalent matching the chosen language).

```text
RequestScope
  orgId: string
  employeeId: string
  mode: demo | live | eval
  principalId: string
  authLevel: fixture | authenticated_owner
  requestId: UUID string

VoiceMatch
  status: matched | unknown | ambiguous | insufficient_audio
  candidateEmployeeId: string | null
  topScore: float | null
  secondScore: float | null
  margin: float | null
  profileVersion: string | null
  reasonCode: string

RunContext
  runId, sessionId, scope, pinnedHarnessVersionId
  transcript, resolvedNowUtc, employeeTimeZone
  selectedMemoryIds, contextBudget, inputSource
```

A server-side internal candidate ID in `VoiceMatch` is not authority. Do not return other employees' identity names or score vectors to an unauthenticated public client. `RequestScope` is never parsed from LLM text.

## Request lifecycle

1. Client begins an explicit capture; show microphone-in-use status.
2. Server validates size/type, decodes/resamples audio and performs speech-quality checks.
3. NovemberAI's existing ASR and the new speaker-embedding step run on the same captured buffer, subject to a one-job audio inference semaphore.
4. Voice service returns a match or rejection. No private data is loaded during this step.
5. Resolver binds a permitted scope, or requires private authentication/confirmation.
6. Create/load an employee-scoped session and create a run with a pinned harness version.
7. Fetch hard policy facts, applicable explicit preferences, relevant notes and short recent history within the context budget.
8. Model proposes typed reads or a response/action plan. Tool broker validates all arguments and supplies the account mapping.
9. Persist run outcome. Prepare a pending action where needed; never interpret 'done' from the model as tool success.
10. Store permitted memory updates with source and idempotency key; extract provisional notes asynchronously if necessary.
11. Present the result on an authorized surface. Generic acknowledgments may be spoken.
12. Explicit feedback or verified task outcomes may enqueue an improvement job.

## Concurrency and ownership

- One active audio capture per desk; a second capture gets `DESK_BUSY` or waits visibly.
- Acquire a per-employee run lock for mutations; independent employees may have separate read-only runs within a small global concurrency cap.
- No global `current_employee` variable for backend tasks. Pass immutable scope explicitly.
- A new speaker does not take ownership of an existing pending action.
- Scope every cache key, including context, token refresh, connector results and idempotency records.
- Different employees use distinct chat histories even when they share the same underlying model client.
- Run headers store model identifier, harness version, fixture snapshot and connector mode for reproducibility.

## Durable states

Run states: `created -> running -> awaiting_approval | completed | failed | interrupted | cancelled`.

Pending action states: `pending -> executing -> succeeded | failed | outcome_unknown`; also `pending -> rejected | expired | invalidated`.

On restart, mark nonterminal in-process work interrupted. Do not automatically retry external writes that might already have succeeded. Reconcile or ask for a new verified action. Reads may be retried with limits.

MVP implementation may use in-process background workers backed by persisted run/action records. That is not a durable distributed job scheduler. If restart-resume is incomplete, report it; do not claim hours-long autonomous operation.

## Failure behavior

- Atlas unavailable: no in-memory-only success claim. Show persistence unavailable and stop consequential operations.
- Voice service unavailable: offer visibly labeled text-demo mode for fictional data; do not silently reuse the last identity.
- STT uncertain: ask for a repeat; no private memory update.
- Embedding/index unavailable: use scoped direct preferences and bounded lexical retrieval, labeled degraded.
- LLM unavailable: deterministic UI/tool fixtures may remain testable, but no fake generated answer or improvement result.
- OAuth expired/revoked: mark only that connection unavailable. Never borrow another employee's token.
- Permission mismatch: reject before tool access, with a redacted audit record.
- Candidate evaluation fails: retain current harness and log the rejection.

## Source and trust boundaries

Browser pages, incoming emails, calendar descriptions and retrieved notes are data, not executable policy. They cannot change identity, approve an action, add tools or instruct the optimizer to bypass tests. Keep their text in explicitly delimited evidence blocks and enforce the separation in code, not merely in a prompt.

See [voice/identity](04-VOICE-AND-IDENTITY.md), [memory](05-MEMORY-AND-CONTEXT.md), [tools](06-TOOLS-AND-APPROVALS.md), and [harness improvement](07-HARNESS-IMPROVEMENT.md) for the detailed contracts.
