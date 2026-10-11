# MARCH
## Multi-user Adaptive Recursive Context Harness

One desk assistant. Three private employee workspaces. A harness that improves only when tests prove it.

**Status:** build specification, prepared October 11, 2026 for the Harness Engineering & Model Wrangling #SFTechWeek hackathon. No MARCH code exists yet. No accounts, databases, credentials or deployments were created by this package.

## Start here

1. Create the MARCH repository in the November GitHub organization (you control naming and visibility; it must be public before submission).
2. Copy this folder into it.
3. Make the NovemberAI checkout available to the coding agent.
4. Give the agent the kickoff prompt below.

### Coding-agent kickoff prompt

> Read AGENTS.md, then docs/13-NOVEMBERAI-REUSE.md and docs/09-IMPLEMENTATION-PLAN.md. These are a plan, not existing code. First inspect the NovemberAI checkout and write NOVEMBER-REUSE-MAP.md: language, launch command, and exact entry points for capture, ASR, transcript checks, intent schema/compiler, policy, approvals and TTS, plus what is implemented vs only planned. Reuse those components as-is for ASR and intent; do not build a second ASR or intent parser. Preserve uncommitted work and running processes; do not fetch, reset, push or change repository visibility. Then build milestones M0-M5 in order against the event MongoDB Atlas sandbox, using the partner products in docs/14 within their time boxes. Use fictional fixture employees and fixture tools; no live accounts, real sends or paid usage without my explicit approval. At each cut line take the stated fallback, label it, and continue. Keep IMPLEMENTATION-STATUS.md current with real commands and results. Never fake voice recognition, evaluation results, or integrations.

## Documents

- [AGENTS.md](AGENTS.md): build contract, reuse mandate, invariants.
- [01 Product and scope](docs/01-PRODUCT-AND-SCOPE.md)
- [02 Architecture](docs/02-ARCHITECTURE.md)
- [03 MongoDB data model](docs/03-MONGODB-DATA-MODEL.md)
- [04 Voice and identity](docs/04-VOICE-AND-IDENTITY.md)
- [05 Memory and context](docs/05-MEMORY-AND-CONTEXT.md)
- [06 Tools and approvals](docs/06-TOOLS-AND-APPROVALS.md)
- [07 Harness improvement](docs/07-HARNESS-IMPROVEMENT.md)
- [08 API and UI](docs/08-API-AND-UI.md)
- [09 Three-hour implementation plan](docs/09-IMPLEMENTATION-PLAN.md)
- [10 Tests and evaluations](docs/10-TESTS-AND-EVALUATIONS.md)
- [11 Operations, demo, submission](docs/11-OPERATIONS-AND-DEMO.md)
- [12 Research and decisions](docs/12-RESEARCH-AND-DECISIONS.md)
- [13 NovemberAI reuse contract](docs/13-NOVEMBERAI-REUSE.md)
- [14 Partner products](docs/14-PARTNER-PRODUCTS.md)

## Built before the event (to be completed by the agent)

NovemberAI: voice capture, ASR, transcript checks, intent compiler, deterministic policy, approval/cancellation. Link and commit go here.

## Built during the event (planned)

Speaker identification and enrollment; per-employee MongoDB context, memory and Vector Search retrieval; scoped tool broker and owner-bound approvals; harness versioning, evaluation suite and gated promotion; Raindrop tracing; optional Modelence hosting and ElevenLabs voice; demo UI.

## The minimum convincing demo

- Three consenting people recognized on new phrases; a fourth voice rejected.
- Each person's preferences persist in Atlas and stay separate as speakers alternate.
- The same request yields employee-specific results through scoped fixture tools.
- A recorded failure produces one real allowlisted harness change, tested on the same cases, promoted or honestly rejected.
- A cross-employee request and an unknown speaker fail safely.

## Not claimed

No production voice authentication, no live Google or Aside integration today, no measured results until the system runs, and no statistical significance from a small evaluation suite.
