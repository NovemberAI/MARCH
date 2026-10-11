# MARCH
## Multi-user Adaptive Recursive Context Harness

One shared office desk assistant. It recognizes enrolled colleagues by voice, opens each one's **private MongoDB-backed workspace**, runs employee-scoped tools under exact-action approval, does read-only web research, and **improves bounded parts of its own harness only when measured evaluations show it got better**.

Built for the Harness Engineering & Model Wrangling hackathon (Statement 1: Recursive Harnessing), October 11, 2026, on the event MongoDB Atlas sandbox.

---

## The recursive harness loop (the main idea)

```
real runs ──► structural failures / employee feedback ──► MongoDB evidence
     ▲                                                          │
     │                                          fixed optimizer (local LLM) proposes ONE patch
     │                                          to ONE allowlisted, bounded config path
     │                                                          │
 promote (compare-and-set)  ◄── hard gates ◄── paired eval: baseline vs candidate
 or reject with reasons           (critical cases, noise band,   (march_eval, fixture-only,
                                   per-case regressions)          cached November intents,
                                                                  real Atlas Vector Search)
```

- **What can change:** only `HarnessConfig` fields in `march/harness.py` `ALLOWLIST`, within bounds: retrieval depth, pinning explicit preferences, a scheduling preference pass, and similar. Each version is immutable and has its own `configHash`.
- **What cannot change:** identity, scope, approvals, credentials, evaluators, expected outcomes and source code. These are not representable as patches (`tests/test_harness.py`).
- **Gates (doc 07):**
  - zero critical-case failures (isolation, negation, approval);
  - mean dev+val gain greater than the baseline noise band across 3 paired repeats;
  - neither split regresses;
  - at least one previously failing case is fixed;
  - no per-case regressions.
  The held-out test split is reported but never shown to the optimizer.
- **Promotion** is a compare-and-set on `employees.activeHarnessVersionId`, so a stale candidate cannot overwrite. Runs that are in flight keep their pinned version. Rollback is available from the UI.
- **Honesty guards:**
  - evaluation has no live side effects (browser disabled, fixture tools only);
  - an evaluation is invalidated if any case falls back from Atlas Vector Search to lexical recall;
  - token usage is reported as unavailable rather than zero.

### Measured results (real, from Atlas `march_eval.evaluations`)

See `IMPLEMENTATION-STATUS.md` → "M4 cycles" for the exact evaluation IDs, rates, patch and decision.

## What runs

| Capability | How |
| --- | --- |
| Voice → text → intent | **NovemberAI** (reused, unmodified): browser capture worklet, `VoiceLoop`, Silero VAD, "Hey November" wake word / push-to-talk, faster-whisper `small.en` (local), transcript checks, intent compiler (local Qwen via Ollama), deterministic policy |
| Who is speaking | MARCH: SpeechBrain ECAPA on the **same buffer** November captured, so no second mic stream. Matched / unknown / ambiguous / insufficient. Encrypted profiles in Atlas; consent, verification and revoke |
| Private workspaces | Server-owned `RequestScope`; every repository method adds `mode/orgId/employeeId`; the browser cannot choose an `employeeId` |
| Memory | Typed explicit preferences (read-your-writes) plus notes recalled with **Atlas Vector Search Automated Embedding** (`autoEmbed`, voyage-4-lite) with scope pre-filters; forget with tombstones |
| Tools | Fixture calendar slot finder and email preparation; exact payload-hash approval, owner-bound, single-use, simulated send; November's "do not send" keeps a draft non-dispatchable |
| Web research | **NovemberAI's Aside `BrowserAdapter`** (reused): real local Aside browser search/open/read, **read-only** (MARCH refuses every click/fill) |
| Talk-back | ElevenLabs TTS for generic template acknowledgments only, never private content (enabled when `ELEVENLABS_API_KEY` is set) |

## Built before the event (reused, not claimed as new)

**NovemberAI**, https://github.com/NovemberAI/november, local checkout at commit `ee7a476` plus the owner's uncommitted working-tree changes (see `NOVEMBER-REUSE-MAP.md`). Reused components:
- audio capture worklet;
- `VoiceLoop` state machine, VAD, wake word, Whisper ASR;
- transcript normalization and credential rejection;
- intent schema, compiler and local-model editor;
- deterministic policy;
- Aside browser adapter and local planner.

MARCH imports these from the checkout and does not copy them.

## Built during the event (October 11, 2026)

Everything under `march/`, `tests/`, `scripts/` and `evals/`:
- reuse map;
- Atlas data layer and scoped repositories;
- fixture tools;
- payload-hash approvals;
- speaker identification (enrollment, calibration and replay tools);
- per-employee memory with Automated Embedding retrieval;
- the versioned harness, evaluation suite, optimizer and gated promotion/rollback;
- read-only browser integration;
- ElevenLabs talk-back;
- the desk UI.

The planning documents in `docs/` were written the same day, before the code.

## Run it

```sh
# 1. NovemberAI's local models (from its own runtime)
cd ~/november-1 && OLLAMA_MODELS="$PWD/.runtime/models" OLLAMA_NO_CLOUD=1 .runtime/ollama/ollama serve
# 2. MARCH (needs .env with MONGODB_URI for the event Atlas sandbox)
cd ~/MARCH && .venv/bin/python -m march.server        # http://127.0.0.1:8780
# tests and evaluation
.venv/bin/pytest -q -p no:cacheprovider
MARCH_SUITE=suite_v2 .venv/bin/python scripts/run_eval.py baseline
.venv/bin/python scripts/run_eval.py cycle emp_asha
```

## Not claimed

- Voice identification routes demo workspaces only; it is not authentication.
- All employees, calendars, contacts and emails are fictional, and sends are simulated.
- The browser is one shared local Aside session, limited to public pages with no employee logins, because per-employee browser isolation is unverified.
- The evaluation suite is small (24 cases), so no statistical significance is claimed.
- Suite v2's larger memory history was added after suite v1's baseline passed every dev/val case. That is disclosed in `IMPLEMENTATION-STATUS.md`.
