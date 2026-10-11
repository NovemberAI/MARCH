# AGENTS.md: MARCH build contract

## Mission

Build MARCH, the **Multi-user Adaptive Recursive Context Harness**, in about three hours for the Harness Engineering & Model Wrangling hackathon (submissions due 5:00 PM Pacific, October 11, 2026). One shared desk assistant recognizes three enrolled colleagues by voice, keeps a private MongoDB-backed workspace for each, executes employee-scoped tools with exact-action approval, and improves bounded parts of its harness only when measured tests say it got better.

Target track: **Statement 1, Recursive Harnessing.** Build in the event's MongoDB Atlas sandbox.

## Read order

1. This file.
2. [NovemberAI reuse contract](docs/13-NOVEMBERAI-REUSE.md). Do this first.
3. [Three-hour implementation plan](docs/09-IMPLEMENTATION-PLAN.md).
4. [Partner products](docs/14-PARTNER-PRODUCTS.md).
5. The doc for the milestone you are on: [architecture](docs/02-ARCHITECTURE.md), [MongoDB data model](docs/03-MONGODB-DATA-MODEL.md), [voice/identity](docs/04-VOICE-AND-IDENTITY.md), [memory](docs/05-MEMORY-AND-CONTEXT.md), [tools/approvals](docs/06-TOOLS-AND-APPROVALS.md), [harness improvement](docs/07-HARNESS-IMPROVEMENT.md), [API/UI](docs/08-API-AND-UI.md).
6. [Tests and evaluations](docs/10-TESTS-AND-EVALUATIONS.md) before claiming any milestone done.

These documents are a plan. Nothing in them is implemented yet. Do not describe proposed modules, endpoints, tests, accounts or results as existing.

## Reuse mandate

- **ASR and intent processing come from the user's existing NovemberAI code and architecture.** Capture, VAD/wake word, ASR, transcript checks, intent schema, intent compiler, deterministic policy, approval and cancellation are reused as-is.
- Do not build a second ASR pipeline, a second intent parser, or a new LLM classifier for the same job. Do not use ElevenLabs or any hosted STT for transcription.
- Start by inspecting the NovemberAI checkout and writing `NOVEMBER-REUSE-MAP.md` (entry points, language, launch command, what is implemented vs planned, test results).
- If NovemberAI's voice pipeline is not implemented, tell the user immediately. Use its text compiler with a labeled typed-input path unless the user approves an ASR choice.
- MARCH lives in the user's November GitHub organization. The user creates the repository and controls visibility; never create orgs, change visibility, push, or transfer repositories without explicit instruction.
- Event rules forbid presenting existing work as new. The README must separate "Built before the event" (NovemberAI) from "Built during the event" (MARCH).

## Use ready-made products

Use existing products wherever they remove real work, one owner per responsibility, each with a time box. Defaults:

- MongoDB Atlas (event sandbox): all MARCH state. Required.
- Atlas Vector Search with Automated Embedding (`autoEmbed`) for scoped memory retrieval, so no embedding pipeline is written. Labeled lexical fallback if the sandbox lacks it.
- MongoDB MCP Server and Agent Skills: for the coding agent during development only, never as a runtime tool.
- SpeechBrain ECAPA (local): speaker identification, the one new voice component.
- Raindrop: redacted run traces, signals, baseline vs candidate comparison.
- Modelence: host the thin Node/TS web layer only, behind a 15-minute fail-fast gate. Its runtime is Node.js-only with one process; do not port Python code to fit it.
- ElevenLabs: optional TTS voice for generic acknowledgments.
- Google APIs and Aside MCP: not on today's critical path.

Do not add LangChain/LangGraph, another vector store, Redis, queues, or extra worker processes.

## Non-negotiable invariants

1. **Voice routes; it does not authorize.** A voice match can select fictional demo data. Live private data needs an independently authenticated owner session.
2. **Unknown means unknown.** Low score, small margin, short audio, or ambiguity never falls back to the closest or last employee.
3. **Scope is server-owned.** `orgId`, `employeeId`, `mode` and authorization never come from model output or untrusted request fields.
4. **No shared private context.** Sessions, prompts, caches, retrieval, traces, pending actions and connectors are per employee.
5. **No model-generated database queries.** Typed repository methods add mandatory scope filters.
6. **No external write without fresh owner approval** of the exact payload hash. Changed payload means new approval. November's "draft but don't send" constraints survive to the dispatcher.
7. **No deletion-capable OAuth scopes,** no live accounts, and no paid services without explicit user approval.
8. **Self-improvement cannot touch security.** Only allowlisted harness config fields within bounds. Identity, scope, approvals, credentials, evaluators, expected outcomes and source code are immutable to the optimizer.
9. **Evaluation never has live side effects.** Separate `march_eval` database and fixture-only adapters.
10. **No fabricated proof.** Report real scores, real diffs, real voice results. Label fixtures, fallbacks, manual identity selection and anything simulated.
11. **Consent and deletion.** Enroll only consenting people, keep no raw audio, support revoke and forget.
12. **Secrets stay out of git and out of telemetry.** No tokens, URIs, voice profiles or private bodies in commits, logs, Raindrop, or the UI.

## Repository discipline

Inspect the local tree and running processes first. Preserve uncommitted work and existing NovemberAI files. Do not fetch, pull, reset, clean or rebase unless asked. Do not launch duplicate servers or model downloads. Keep `IMPLEMENTATION-STATUS.md` current with real commands and results.

## Work sequence (time-boxed)

- 1:45 M0 reuse map, repo scaffold, Atlas connection, seed fixtures.
- 2:00 M1 typed input -> November intent -> scoped fixture tools -> run + pending action in Atlas.
- 2:30 M2 speaker identification on November's captured audio, three enrollments, unknown handling.
- 3:05 M3 scoped memory with Automated Embedding Vector Search and read-your-writes.
- 3:30 M4 harness versions, eval suite, one bounded improvement cycle, Raindrop traces.
- 4:05 M5 Modelence gate, polish, README, status.
- 4:30 demo recording; user submits by 5:00.

Each milestone has a cut line in the plan. At the cut line, take the fallback, label it, and move on. Never trade M1-M4 for M5 polish.

## Definition of done for today

Real Atlas persistence; three real voice enrollments routed to separate contexts with unknown-speaker rejection; persistent memory that changes behavior; one real measured improvement cycle with promotion or honest rejection; all isolation and approval tests passing; README disclosing reused NovemberAI components; demo recorded from the running system.

## Completion report

Changed files, exact commands with pass/fail, what works, what is simulated or fallback, any external effects, evaluation counts, blockers, and launch steps. Do not publish, submit, send email, or incur charges without explicit user approval.
