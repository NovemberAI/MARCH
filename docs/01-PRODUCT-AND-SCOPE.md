# 01. Product and scope

## Product sentence

MARCH is one desk-side assistant that recognizes three enrolled colleagues, gives each a private persistent workspace, acts through that colleague's connected tools, and learns better retrieval and execution workflows from measured outcomes.

Same assistant persona, different private context. A separate model per employee is unnecessary.

## Event alignment

Source checked October 11, 2026: [official participant guide](https://cerebralvalley.ai/e/mongodb-sftw-hackathon/details).

- Primary track: **Statement 1, Recursive Harnessing**. The harness should adapt rules, context policies and workflow to a user/task.
- Do not claim the secondary track's billion-token or weeks-long operation. Persistent memory alone does not establish that capability.
- Finalists must use the **provided MongoDB Atlas sandbox**, not merely any MongoDB deployment.
- Repository must be public. Submission includes an accessible one-minute demo video.
- Demo must distinguish features built during the hackathon from pre-existing tools and libraries.
- No basic RAG apps, Streamlit apps, personality analyzers or dashboard-first products.
- First-round weights: technical demo 35%, implementation difficulty 30%, impact 20%, creativity 15%.
- Guide lists October 11 submissions at 5 PM Pacific and an additional Raindrop RSI prize.

The useful framing is not 'RAG plus voice'. The original work is identity-aware routing, isolated context and execution, and measured per-employee harness adaptation. Avoid inferring personality, demographics, emotions, health or employee performance from voices.

## Users and fixture identities

Exactly three synthetic employee records:

- `emp_asha`, display name Asha: America/Los_Angeles, prefers afternoon meetings and concise email.
- `emp_ben`, display name Ben: America/New_York, prefers mornings and fuller email explanations.
- `emp_casey`, display name Casey: Europe/London, prefers 25-minute meetings and a 15-minute buffer.

These are test fixtures, not facts about actual employees. Each consenting volunteer maps their voice to one fixture identity. Use `.test` email domains in fixtures; never make them live recipients.

## Core journeys

### Enrollment

Operator explains collection and retention. Participant opts in, chooses a fixture identity, records multiple clean clips, tests a new phrase, and sees completion only after the profile is persisted. Enrollment identity is explicitly selected and confirmed, not inferred by the model.

### Personalized request

Asha presses the talk control and asks for meeting options. MARCH recognizes her, displays the matched fixture identity, retrieves only her scheduling preferences and calendar fixture, and returns valid options. Ben repeats the same words and gets a different result from his own data.

### Memory continuity

Casey states a preference, then another employee speaks. When Casey returns, the assistant recalls that preference with source and time. The other employees do not inherit it. Restarting the backend does not erase accepted memory.

### Execution

The assistant prepares a concrete email or calendar proposal, showing account, recipients, dates, timezone and content. The owner approves the exact proposal. In demo mode the fixture provider records a simulated action. In live mode only an authorized, independently authenticated owner can approve an enabled action.

### Harness improvement

A preference already exists, but a baseline retrieval/workflow misses it. A correction and task trace produce a small structured policy change. The app evaluates old and new versions on identical fixtures, displays measured differences, and promotes or rejects the candidate. Further run history can drive another iteration.

### Safe rejection

Unknown speaker, ambiguous audio, another person's approval, a request for another employee's private data, or missing connector all produce an explicit safe state. No action is attributed to the last speaker by default.

## Must ship

- Consent-based enrollment for three people and unknown-speaker handling.
- Push-to-talk, one speaker at a time; transcript and identity status visible.
- MongoDB-backed memory, sessions, runs and harness versions.
- Server-enforced employee scope at every boundary.
- Fixture calendar/email tool execution with clear simulation labeling.
- Real structured harness proposal and automated sandbox evaluation.
- Exact-action approval flow and cross-user rejection.
- Reproducible tests, startup instructions and public-safe demo assets.

## Valuable but optional

- Atlas Vector Search with Automated Embedding (Voyage AI managed by MongoDB), if the sandbox supports it. MongoDB persistence is mandatory; absence of vector indexing is an explicitly labeled reduced capability.
- Real Google read-only connectors, after account consent and configuration.
- Approved live email sending using a narrowly scoped token.
- Optional generic TTS acknowledgments.
- One second improvement iteration if the first is stable.

## Explicit non-goals

- Always-on workplace surveillance, meeting transcription, simultaneous speaker separation, employee analytics or emotion/personality inference.
- Training/fine-tuning a speaker model or LLM.
- Fully autonomous code rewriting or security-policy evolution.
- Arbitrary browser control, desktop-app automation, multiple cloud VMs or a custom device.
- Cross-employee sharing, manager access to employee memory, organization-wide search, delegating actions between employees.
- Production deployment, compliance certification or voice-only authentication.

## User-visible success criteria

1. Recognizes new utterances from all three enrollees and rejects unknown/ambiguous cases in the test set.
2. The same request returns correctly personalized results for different employees.
3. Accepted memories remain available after restart.
4. Every scoped isolation and approval test passes.
5. A candidate changes an actual runtime policy; evaluation is real and repeatable.
6. If promoted, candidate quality improves beyond the measured baseline noise without privacy regressions. Otherwise the app visibly rejects it.
7. Every live/mock/fallback state is truthful.

No target here is a claimed result. Small hackathon tests do not establish production security or population-wide recognition accuracy.
