# 12. Research basis and decisions

## Papers and what MARCH takes from each

| Paper | Mechanism | What MARCH uses | What MARCH does not claim |
| --- | --- | --- | --- |
| Recursive Harness Self-Improvement (RHI), arXiv 2607.15524 | Harness as prompt-level spec of roles, instructions, contracts, hops; revise from pairwise comparison history against previous version | Improve information flow and workflow steps, not reasoning length; compare candidate with its parent; keep revision history | RHI's results come from 30 synthetic ML research tasks with LLM judges; no evidence for office assistants |
| Self-Harness, arXiv 2606.09498 | Weakness mining from traces, minimal proposals tied to one failure, accept only with no held-in/held-out regression | One failure -> one small patch -> regression test | Benchmark results on Terminal-Bench, SWE-bench Verified, AppWorld; authors note possible benchmark-specific edits |
| RRSI, arXiv 2609.24972 | Regularized evolution: edit budget, history of tried edits, leakage critic on the shipped diff, noise band from repeated baseline runs, cost justification | One edit per candidate, rejected-edit history, no fixture literals in shipped config, measured noise band, token/latency cap | Its tuned hyperparameters and multi-round schedules are out of scope for a 3-hour build |
| ACE, arXiv 2510.04618 | Itemized playbook updated by small deltas (Generator, Reflector, Curator), avoids context collapse | Per-employee small procedural lessons, deterministic merge, no full rewrites | Degrades without reliable feedback signals, per the paper |
| A-MEM, arXiv 2502.12110 | Atomic linked notes with keywords, tags, timestamps, embeddings; memory evolution | Atomic source-linked notes; limited link expansion | Evaluated on conversational recall, no multi-user isolation; MARCH skips automatic rewriting of old notes |

Links: https://arxiv.org/abs/2607.15524, https://arxiv.org/abs/2606.09498, https://arxiv.org/abs/2609.24972, https://arxiv.org/abs/2510.04618, https://arxiv.org/abs/2502.12110

## Key decisions

1. **One shared assistant, per-employee data and harness versions.** No model per employee.
2. **Reuse NovemberAI for ASR, intent, policy.** Mandated by the user; disclosed per event rules.
3. **Speaker identification, not diarization.** Enrolled-profile matching with explicit unknown handling.
4. **Voice is routing, not authorization.** Live private data needs an authenticated owner session.
5. **One shared MongoDB collection per entity with scope fields,** following MongoDB multi-tenant Vector Search guidance, plus mandatory server-side scope in code.
6. **Fixture tools first.** Live Google connectors and Aside MCP are optional and gated.
7. **Harness edits are allowlisted config patches.** No source-code self-modification.
8. **Deterministic evaluation gates.** Isolation and approval failures veto any quality gain.
9. **Partner products only where they remove work,** each with a time box ([14](14-PARTNER-PRODUCTS.md)).

## Open assumptions to verify early

- NovemberAI's language, implemented phases, and callable entry points.
- Whether the event Atlas sandbox tier supports Automated Embedding and Vector Search indexes.
- Whether Modelence deploy works for the Node layer and accepts the event Atlas URI.
- Speaker-ID accuracy in the venue's noise with the laptop microphone.
- Which LLM provider credentials are available for the optimizer and any personalization step.

## Event sources

- Participant guide: https://cerebralvalley.ai/e/mongodb-sftw-hackathon/details
- MongoDB resource guide (linked from the participant guide as "MongoDB Builder Guide")
- Event Discord partner channels: MongoDB, AWS (Kiro), ElevenLabs, Modelence, Raindrop
