# HANDOFF (for the next model/session)

Read `AGENTS.md`, then this file, then `IMPLEMENTATION-STATUS.md` and `NOVEMBER-REUSE-MAP.md`.

## Current state (2026-10-11 ~15:05 PDT)

- M0 through M4 code is complete. The first local commit is `e37148d`; later work is uncommitted. Nothing has been pushed.
- Atlas: `.env` points at the **official SFTW sandbox** (`cluster0.qkufdh`; the old personal cluster `oq0rmd9` is no longer used, and its .env line is backed up in `.runtime/`). It is local only, gitignored and chmod 600, and must never be printed or committed. Databases `march_demo` and `march_eval` are seeded. The autoEmbed index `memory_autoembed_v1` is READY in both.
- NovemberAI is at `/Users/shashwatraj/november-1`. Never modify it. It is imported through `.venv/.../november_local_checkout.pth`; `march` is importable from scripts through `march_local.pth`.
- Processes:
  - Ollama from November's runtime: `cd ~/november-1 && OLLAMA_MODELS="$PWD/.runtime/models" OLLAMA_NO_CLOUD=1 .runtime/ollama/ollama serve`. Check with `curl localhost:11434/api/version` first.
  - MARCH server: `.venv/bin/python -m march.server` on port 8780.
  - Do not start duplicates. Before restarting, check `/api/voice/status` for an in-progress enrollment.
- Voice: the code is done. Real volunteers still have to enroll in the UI, then run `scripts/calibrate_voice.py <labels…>` and restart the server.
- TTS: `march/tts.py` is wired to `POST /api/tts` and UI `talkBack()`. It speaks only template acknowledgments and does nothing until `ELEVENLABS_API_KEY` is in `.env`.
- Raindrop: `march/telemetry.py` traces redacted runs and evaluations. It does nothing until `RAINDROP_WRITE_KEY` is in `.env`.
- Browser: `march/browser.py` reuses November's `BrowserAdapter` and is read-only. The planner is `qwen3.5:9b`, set via `NOVEMBER_BROWSER_MODEL` in `.env`.

## Recursive harness (the main focus)

- `march/harness.py`: baseline config (doc 07), ALLOWLIST and bounds, immutable versions, CAS promote/rollback.
- `march/evaluation.py`: suite at `evals/cases/suite_v1.json`; real November outputs cached in `evals/compiled/suite_v1.november.json`. Fixture memories come from `FIXTURE_MEMORIES`, and `suite_v2` adds 20 ordinary history notes per employee.
- `march/improve.py`: `run_cycle` uses the local optimizer (`qwen3:4b-instruct-2507` via Ollama, JSON schema), 3 paired repeats and gates. Results go to `march_eval.evaluations`.
- The UI Harness card runs a cycle (`POST /api/harness/improve`), shows the decision, diff and counts, and offers rollback.
- The sandbox's Voyage autoEmbed is rate-limited, so recall retries with backoff and evals cache each unique query once. A full cycle takes several minutes.

## Tests

`.venv/bin/pytest -q -p no:cacheprovider`: 62 passed (isolation/approval, voice, memory, harness gates, TTS, telemetry redaction).
