# 14. Partner products and ready-made services

Goal: use existing products wherever they remove real work, with one owner per responsibility, and drop any product that fails its time box. Checked October 11, 2026 from the official participant guide, the MongoDB resource guide, the event Discord partner channels, and vendor documentation. Offers, credits and limits can change; re-check at the booth if something matters.

## Summary

| Product | Role in MARCH | Critical path? | Time box |
| --- | --- | --- | --- |
| MongoDB Atlas (event sandbox) | Canonical store: employees, memories, sessions, runs, actions, harness versions, evaluations | **Yes, required for finalists** | 15 min to connect |
| Atlas Vector Search + Automated Embedding | Scoped semantic memory retrieval without writing embedding code | Strongly preferred | 20 min |
| MongoDB MCP Server + Agent Skills | Coding-agent productivity: inspect collections, write queries, create indexes | Dev-time only | 10 min |
| NovemberAI (user's own) | ASR, intent compiler, policy, approvals | **Yes, mandated reuse** | 15 min reuse map |
| SpeechBrain ECAPA | Speaker identification (new; November has none) | Yes | 35 min |
| Modelence | Host the Node web/control plane | Optional, gated | 15 min to first live URL |
| Raindrop | Agent traces, signals, experiment comparison for the improvement loop | Recommended (RSI prize) | 20 min |
| ElevenLabs | Natural TTS for short generic acknowledgments | Optional | 15 min |
| Kiro / Cursor | Coding agents for building faster | Dev-time only | 0 min on critical path |
| Google Calendar/Gmail APIs | Live connectors | Optional, after fixtures | Skip unless time remains |
| Aside MCP | Browser execution | Disabled behind the isolation gate | Skip for this build |

## MongoDB Atlas (required)

- Use the Atlas sandbox from the event email. The guide states finalists must build in that sandbox cluster. Do not substitute another cluster, including a Modelence-provisioned one, for the final demo unless an organizer confirms it counts.
- Put the connection string only in environment secrets.
- Automated Embedding: create a Vector Search index of type `autoEmbed` on `memories.text`, with `mode`, `orgId`, `employeeId`, `status` as filter fields. MongoDB then generates and syncs embeddings with a Voyage AI model at index and query time, so MARCH does not need its own embedding pipeline. Verify the sandbox tier supports it in the first 20 minutes; if not, fall back to a `vector` index with a configured embedding provider, or to the labeled lexical fallback. See [Vector Search overview](https://www.mongodb.com/docs/atlas/atlas-search/vector-search/) and [multi-tenant guidance](https://www.mongodb.com/docs/vector-search/deployment/multi-tenant-architecture/).
- The multi-tenant docs show `autoEmbed` with `indexingMethod: flat` plus a `tenant_id`-style filter field, which matches three small employee partitions.
- MongoDB MCP Server and Agent Skills: connect them to the coding agent only, with a development database user. They are not runtime tools for MARCH employees. Links from the event resource guide: [Agent Skills](https://www.mongodb.com/docs/agent-skills/), [MCP Server](https://www.mongodb.com/docs/mcp-server/get-started/).
- The event #mongodb-specific-questions channel had no posts when checked.

## Modelence (optional hosting)

Verified facts:
- Official deploy docs state the image runs Node.js only, supports exactly one long-running service process, and lists Python projects, second worker processes, Docker Compose, and custom Dockerfiles as incompatible. The server must listen on `process.env.PORT`.
- Modelence injects a provisioned Atlas URI as `MONGODB_URI`. Secrets are declared in `modelence.config.json` and set in the dashboard. Docs also describe connecting an external MongoDB.
- The Modelence hackathon page and event guide describe credits for deploying, but amounts differ: the resource guide and Modelence hackathon page say $100, while a Modelence post in the event Discord says $50. Treat the amount as unconfirmed.
- Agent path: "Use https://modelence.com/skill.md to deploy to Modelence". Review what the skill does before letting an agent run it.

How MARCH uses it:
- Host only the thin Node/TypeScript web app: UI, API routes, MongoDB access, harness evaluation runner if it fits in the single process.
- Override `MONGODB_URI` with the event sandbox URI, or confirm with the Modelence table that their provisioned DB is inside the event sandbox.
- The local NovemberAI process connects outbound to the hosted app. No tunnel into the laptop.

Fail-fast gate (stop at the first "no"):
1. Is the MARCH web layer Node/TS, with no ASR or intent logic inside it?
2. Can you sign up without payment?
3. Does the first deploy reach a live URL with `/health` returning 200 within 15 minutes?

If any answer is no, run MARCH locally and say hosting is deferred. Do not rewrite a Python service into Node to fit Modelence.

Sources: https://docs.modelence.com/hackathon/mongodb-2026, https://docs.modelence.com/deploy/setup, https://modelence.com

## Raindrop (recommended)

- Purpose: trace each run (identity status, retrieved memory IDs, tool calls, outcome) and track signals that feed the improvement loop; use its experiments to compare baseline and candidate harness versions.
- Provides Python and TypeScript SDKs and an HTTP API. The quickstart CLI writes a write key to `.env` and installs coding-agent skills and an MCP server.
- Event Discord: 14-day Pro trial without a credit card; a workshop page is linked. The event also lists a Raindrop RSI prize.
- Privacy: send redacted traces. No raw audio, voice embeddings, OAuth tokens, or full email bodies. Use fictional fixture data in the demo.
- MongoDB remains the authority for promotion decisions; Raindrop is evidence and visualization.
- Do not let the CLI overwrite an existing `.env`; merge keys manually.

Source: http://raindrop.ai/docs

## ElevenLabs (optional)

- Purpose: higher-quality speech for short, generic acknowledgments ("Asha, your draft is ready on your screen"). Private content is not spoken by default.
- Do not use ElevenLabs Transcribe or Agents for ASR or intent; that would duplicate NovemberAI.
- If NovemberAI already has TTS, keep it and add ElevenLabs only as a switchable voice backend.
- Free credits: per the event's ElevenLabs guide, one month of the Creator plan via coupon redemption in the ElevenLabs Discord using the registration email.

## Coding tools (dev-time only)

- Kiro IDE/CLI (AWS): free tier 50 credits per month, no card, per the event AWS channel. Kiro Crew is not needed.
- Cursor: event credits via the guide's redemption link, valid Oct 11-12.
- Use whichever coding agent is already set up. Do not spend the time box switching tools.

## Speaker identification (not a partner)

NovemberAI has no speaker identification, so MARCH adds it. Use local SpeechBrain `speechbrain/spkrec-ecapa-voxceleb`. Picovoice Eagle is an alternative but requires an access key and account. Do not send biometric audio to a cloud service.

## Products not to add today

LangChain/LangGraph frameworks, a second vector database, Redis, Kafka, a separate queue worker, a second ASR, and Kiro Crew. They add surface area without solving a current blocker.
