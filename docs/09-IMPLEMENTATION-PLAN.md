# 09. Three-hour implementation plan

Deadline: submissions due **5:00 PM Pacific, Sunday October 11, 2026**. This plan assumes building starts around 1:45 PM and leaves the last 30 minutes for the demo video and submission. Each block has a cut line: if it is not working at the end of its box, take the stated fallback and move on.

## Order of priority

1. Something end-to-end that runs (text in, scoped answer out, stored in Atlas).
2. Three voices routed to three private contexts.
3. Persistent memory that changes behavior.
4. One real measured harness improvement.
5. Partner integrations that are cheap (Raindrop traces, Automated Embedding).
6. Hosting and polish (Modelence, ElevenLabs).

Never trade 1-4 for 5-6.

## Timeline

### 1:45-2:00 | M0 Reuse map and setup
- Inspect NovemberAI and write `NOVEMBER-REUSE-MAP.md` ([13](13-NOVEMBERAI-REUSE.md)).
- User creates the MARCH repo in the November organization (public before submission). Agent scaffolds only inside it.
- `.env.example` with names only; real values in `.env` (gitignored).
- Connect to the event Atlas sandbox. `/health` reports Atlas ready.
- Seed three fictional employees and fixture calendar/email items into `march_demo` and `march_eval`.
- **Cut line:** if Atlas fails to connect in 15 minutes, ask at the MongoDB table; keep building against fixtures in memory only behind the repository interface, and do not claim persistence.

### 2:00-2:30 | M1 Text-to-scoped-result slice
- Call NovemberAI's existing intent compiler and policy on typed input (no microphone yet).
- `RequestScope`, scoped repositories with mandatory filters, fixture `calendar.find_slots` and `mail.prepare`.
- Run records in MongoDB; pending action with payload hash and owner; approve/reject endpoints.
- Minimal UI: manual fixture identity (labeled), transcript box, result, pending action card.
- Tests: cross-employee read denied; approval by another employee denied; changed payload invalidates approval.
- **Cut line:** if November's compiler cannot be called cleanly, wrap its CLI/function as-is; do not reimplement it.

### 2:30-3:05 | M2 Voice identity
- Hook SpeechBrain ECAPA onto the audio buffer November already captures.
- Enrollment for three consenting volunteers: three clips each, encrypted profile in `voice_profiles`.
- Threshold + margin decision; unknown/ambiguous/insufficient states.
- Quick calibration: each person says two new phrases; one non-enrolled person tries twice. Freeze thresholds.
- UI shows matched fixture name and status. Speaker switch opens the other employee's own session.
- **Cut line:** if model download or audio decoding blocks for more than 20 minutes, ship M3/M4 with the labeled manual selector and record voice ID as incomplete. Do not fake recognition.

### 3:05-3:30 | M3 Memory and context
- Memory write path: explicit preference statements become scoped `memories` with source.
- Automated Embedding Vector Search index on `memories.text` with scope filter fields; scoped `$vectorSearch` + rehydrate.
- Read-your-writes path for explicit preferences.
- "What do you remember about me?" and "forget" for the current employee.
- **Cut line:** if the autoEmbed index is unavailable on the sandbox, use the labeled lexical fallback and keep going.

### 3:30-4:05 | M4 Harness improvement loop
- `harness_versions` with baseline config ([07](07-HARNESS-IMPROVEMENT.md)); active pointer per employee.
- Eval suite: 12 dev, 6 validation, 6 held-out fixture cases including isolation and negation cases ([10](10-TESTS-AND-EVALUATIONS.md)).
- Feedback endpoint; optimizer prompt returning one allowlisted patch; candidate creation.
- Evaluation runner in eval mode; gates; compare-and-set promotion; rollback.
- Raindrop: trace runs and evaluation results (redacted) if signup takes under 10 minutes.
- **Cut line:** if repeated baseline runs do not fit, do one baseline and one candidate run, label the result preliminary, and require manual promotion.

### 4:05-4:30 | M5 Hosting and polish
- Modelence gate ([14](14-PARTNER-PRODUCTS.md)). If it passes, deploy the Node layer with the event Atlas URI; local November bridge posts outbound.
- ElevenLabs voice for generic acknowledgments, only if already trivial.
- Improvement evidence drawer showing the real diff and counts.
- README "built before / built during" sections; `IMPLEMENTATION-STATUS.md`.
- **Cut line:** if deploy is not live by 4:20, demo locally.

### 4:30-5:00 | Demo and submission
- Rehearse once, record the 60-second video ([11](11-OPERATIONS-AND-DEMO.md)).
- User checks repository visibility, secrets scan, video playback, team members, then submits on Cerebral Valley. The agent does not submit.

## Proposed repository layout

Adapt to the language NovemberAI uses. If November is Python, the local bridge is Python and the hosted layer is Node/TS. If November is Node/TS, merge into one service.

```text
march/
  AGENTS.md
  README.md
  IMPLEMENTATION-STATUS.md
  NOVEMBER-REUSE-MAP.md
  .env.example
  docs/                      this specification
  bridge/                    local: November -> MARCH outbound client + speaker ID
    speaker_id/              enrollment, matching, calibration
    november_adapter/        thin calls into existing November modules
  app/                       hosted or local web/control plane
    server/                  API, scope resolver, repositories, tools, approvals, harness
    client/                  React UI
  evals/
    fixtures/                fictional employees, calendars, emails
    cases/                   dev/validation/test JSON cases
    run_eval                 command entry point
  scripts/
    seed                     idempotent seed for demo/eval databases
    create_indexes           idempotent index + search index setup
```

## Environment variables (names only)

`MARCH_MODE`, `MONGODB_URI` (event sandbox), `MARCH_DB_DEMO`, `MARCH_DB_EVAL`, `MARCH_ORG_ID`, `VOICE_PROFILE_KEY_REF`, `LLM_PROVIDER`, `LLM_API_KEY`, `RAINDROP_WRITE_KEY`, `ELEVENLABS_API_KEY`, `MARCH_BRIDGE_DEVICE_SECRET`, `MARCH_PUBLIC_URL`, `PORT`. November keeps its own existing variables.

## Definition of done for today

- M0-M4 working locally with real Atlas persistence, real voice identification for three enrolled people, and a real (possibly rejected) measured improvement cycle.
- All isolation and approval tests passing.
- README discloses reused NovemberAI components.
- Demo video recorded from the actual running system.

Live Google/Aside connectors are explicitly out of today's definition of done.
