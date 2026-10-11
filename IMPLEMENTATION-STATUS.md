# Implementation status

Last updated: 2026-10-11 ~15:00 PDT (clock check: work is ahead of the doc-09 timeline). Only verified facts are listed here.

## Milestones

| Milestone | State | Evidence |
| --- | --- | --- |
| M0 reuse map | **done** | `NOVEMBER-REUSE-MAP.md`; NovemberAI suite: 413 passed (unit+integration, user_flows skipped) |
| M0 scaffold | **done** | `march/` package, `.venv` (Python 3.13.5), `.env.example`, `.gitignore` |
| M0 Atlas connection | **done** (event sandbox `cluster0.oq0rmd9`) | `/health`: `persistence=atlas, atlasReady=true`; ping ok on `march_demo` and `march_eval` |
| M0 seed | **done** in Atlas: 3 employees + 12 fixture items in each of `march_demo` and `march_eval` | `march/fixtures.py`: 3 fictional employees, calendar + contact fixture items, idempotent upserts |
| M1 typed slice | **done, persisted in Atlas** (first Atlas run + session verified by count) | Live smoke: "email Priya about the launch plan" -> November `execute`/`approval_required` -> `mail.send` pending action with payload hash |
| M2 voice ID | **pipeline done; real-volunteer enrollment + calibration PENDING** | Synthetic replay through the real path (November VAD + Whisper `small.en` -> ECAPA on the same buffer): 2 synthetic voices enrolled and verified; held-out Samantha matched emp_asha (0.873 vs 0.028); non-enrolled Moira -> `unknown` (best 0.228), no session or run created. Thresholds are PROVISIONAL (0.40 / 0.08) until `scripts/calibrate_voice.py` runs on real voices. |
| M3 memory | **done** | Atlas `autoEmbed` Vector Search index `memory_autoembed_v1` (voyage-4-lite, filters mode/orgId/employeeId/status) is READY in both DBs. Live: "where is our team retreat" recalled each employee's own "offsite" note (no keyword overlap), scoped. "I prefer morning meetings" -> Casey's next slot search was mornings only (read-your-writes via indexed find). Forget purges text + tombstone. Unit tests use the labeled lexical fallback (mongomock lacks `$vectorSearch`). |
| M4 harness loop | **done: 3 real cycles (no_failures_to_fix, rejected, promoted)** | `march/harness.py` (doc-07 schema, allowlist + bounds, immutable versions, CAS promote/rollback), `march/evaluation.py` (24 cases 12/6/6, cached real November compilations, fixed clock, march_eval, real Atlas vector recall, invalid-recall gate), `march/improve.py` (local Ollama optimizer -> one allowlisted patch -> 3x paired repeats -> gates). Clean baseline v1: dev 12/12, val 6/6, test 4/6 (c05 November clarify; b07 November intent=research for an email command). Cycle evaluation `b4f0699d…`: baseline 1.0/1.0/1.0, so no candidate was proposed. |
| Browser (user-requested critical path) | **working, read-only** | NovemberAI's own `BrowserAdapter` (Aside MCP `--host local`, local Qwen planner) reused unmodified; MARCH refuses every click/fill review. Live: "open https://example.com and summarize the page" -> done, summary + source stored in Ben's run. Live: a MongoDB docs search opened the right page, then stopped at November's 55 KB observation limit. One attempt hit an Aside action error. Planner set to `qwen3.5:9b` via November's own `NOVEMBER_BROWSER_MODEL`; the 4B model looped on read. Disabled in eval mode. |
| M5 hosting/polish | not started | |

## Commands (real results)

```sh
.venv/bin/pytest -q -p no:cacheprovider          # 27 passed (12 isolation/approval + 8 voice + 7 memory)
.venv/bin/python scripts/replay_voice.py http://127.0.0.1:8781 enroll|speak ...   # synthetic replay, eval server
.venv/bin/python -m march.server                  # http://127.0.0.1:8780
curl -s localhost:8780/health                     # 200, persistence=in_memory_fallback_NOT_PERSISTED
```

## What is real and what is simulated

- **Real:** NovemberAI compiler and policy (`november_live_local_models`: qwen3.5:9b editor + qwen2.5:3b classifier via November's own `.runtime` Ollama), server-owned scope, compare-and-set approval.
- **Simulated / fixture:** every employee, calendar, contact and email is fictional. An approved send writes a `simulated_sends` record labeled "SIMULATED fixture send; no email was delivered".
- **Manual:** the manual fixture selector stays, labeled MANUAL. Voice-matched sessions are labeled `voice_match`.
- **Voice:** the only synthetic voice results are from macOS `say` voices in `march_eval`, a pipeline check that is not evidence of real accuracy. `march_demo` has no voice profiles until real volunteers enroll.
- **Test doubles:** the unit tests use mongomock and recorded November outputs (`RecordedCompiler`), labeled in `tests/conftest.py`.

## External effects

None. No accounts were created, no email was sent, no push, no paid service.

## Known behavior

- November's policy sometimes returns `clarify` ("could not reliably preserve the requested action") when the local model's entity is not a literal substring of the command, for example "find a 30 minute slot with Asha tomorrow". This is November's grounding check working as designed, and MARCH does not loosen it. Rehearse the demo phrasing.
- Preference correction is supersede-then-insert, not a multi-document transaction; history is kept through `supersedesId`.
- Recall has no relevance cutoff yet, so an unrelated note can be recalled; for example, the vendor note came back for a slot request. This is a candidate knob for M4.
- The sandbox's Voyage autoEmbed query embedding is rate-limited. Recall retries with backoff; evals embed each unique (employee, query) once per cycle and are invalidated if any case falls back to lexical recall.
- The office browser is one shared local Aside session limited to public pages, with no employee logins. Per-employee browser isolation is unverified (doc 06 gate).

## M4 cycles (real, Atlas `march_eval.evaluations`)

| Suite | What | Result |
| --- | --- | --- |
| suite_v1 (about 10 memories per employee) | baseline v1, all splits | dev 12/12, val 6/6, test 4/6 (c05: November clarify; b07: November intent=research for an email command) |
| suite_v1 | cycle `b4f0699d…` for emp_asha | `no_failures_to_fix`: baseline 1.0/1.0/1.0 over 3 repeats, so no candidate |
| suite_v2 (+20 ordinary history notes per employee; **added after v1 passed, disclosed**) | baseline v1, all splits | dev 10/12, val 6/6, test 4/6. **New real failures c03 and c07**: Casey's explicit 25-minute default was not in semantic top-6 once her history grew, so slots came out at 30 minutes |
| suite_v2 | cycle 1 `2ba36d9d…` for emp_casey | **rejected**. Optimizer proposed `/retrieval/maxContextTokens=5000` (a field not wired in this build). dev+val 0.889 -> 0.889 over 3 paired repeats, noise band 0.0, no case fixed. Held-out test 4/6 -> 4/6. v1 stays active. |
| suite_v2 | cycle 2 `6ac47e73…` for emp_casey | **PROMOTED**. Optimizer (local qwen3:4b-instruct, given that cycle 1 was rejected and the structural evidence `explicit_preference_existed_but_unused:scheduling.default_duration_minutes`) proposed `/retrieval/pinExplicitPreferences=true`. dev+val 0.889 -> 1.000 in all 3 paired repeats; noise band 0.0; fixed c03 and c07; no regressions; no critical failures. Held-out test 4/6 -> 4/6 (remaining failures are November understanding: c05 clarify, b07 intent). Compare-and-set promotion: Casey's active version is now v3 with the patch; Asha and Ben stay on v1. |
