# NovemberAI reuse map

Inspected read-only on 2026-10-11 at 13:56 PDT. Nothing in the NovemberAI checkout was modified.

## Repository

| Item | Value |
| --- | --- |
| Path | `/Users/shashwatraj/november-1` (`/Users/shashwatraj/november` is a README-only clone of the same remote) |
| Remote | `https://github.com/NovemberAI/november.git` |
| HEAD | `ee7a476cd1ec609725a48528a13930bed7ea23fd` ("allow push to talk without wake phrase") |
| Uncommitted work | **Yes, 36 entries.** Tracked modifications include `src/november/policy/engine.py`, `intent/prompt.txt`, `session.py`, `cli.py`, `ui/*`. Untracked Phase 3 code: `src/november/aside/`, `storage/audit.py`. Left untouched. |
| Language | Python, `requires-python >=3.13`; venv `.venv` is Python 3.13.5 |
| Packaging | setuptools, package `november-local` 0.1.0, editable install; lock files `requirements-dev.lock`, `requirements-voice.lock`, `requirements-mcp.lock` |
| Launch | `OLLAMA_MODELS="$PWD/.runtime/models" OLLAMA_NO_CLOUD=1 .runtime/ollama/ollama serve`, then `.venv/bin/november serve --voice` (UI at http://127.0.0.1:8765) |
| One-shot compile | `.venv/bin/november compile "<text>"` (needs Ollama) or `--offline` (deterministic diagnostic grammar) |

Because MARCH imports from the working tree, it runs against **HEAD plus the uncommitted changes**, not against a pinned commit. Recommendation for disclosure: the owner commits the November work in progress so the README can cite one exact commit.

## Entry points and status

Status values: **tested** = implemented and covered by the passing suite below; **partial** = implemented, with known gaps in quality or coverage; **planned** = not present.

| Stage | Entry point | Status |
| --- | --- | --- |
| Audio capture | Browser `ui/voice.js` + `ui/audio-worklet.js` -> `VoiceLoop.feed(pcm, capture_id, sequence)` in `audio/controller.py` (16 kHz float32, 80 ms frames, one mic lease) | tested |
| VAD | `SileroVoiceActivityDetector` in `audio/detectors.py` (`.runtime/voice/silero_vad.onnx`) | tested |
| Wake word | `SherpaWakeWordDetector` ("Hey November", sherpa-onnx KWS zipformer) + ASR-side `WAKE_PREFIX` check; push-to-talk via `VoiceLoop.hold_start()` | tested; noise robustness is a known open issue |
| ASR | `LocalWhisper.transcribe(samples) -> Transcript(text, reliable, duration_ms)` in `asr/local.py` (faster-whisper `small.en`, CPU int8) | tested; 18/20 on clean synthetic speech, real-mic acceptance unmeasured per README |
| **Seam for speaker ID** | `VoiceLoop._transcribe(audio, ...)` receives the full utterance buffer and calls `self.asr.transcribe(audio)`; the recognizer is injected via the `SpeechRecognizer` protocol (`audio/interfaces.py`) | MARCH can wrap the recognizer to read the **same buffer** with no second mic stream |
| Transcript checks | `input.normalize()` (length cap, credential rejection, NFKC, invisible chars) in `input.py`; reliability gate + wake-prefix + filler stripping in `_transcribe` | tested |
| Transcript editing | `LocalTranscriptEditor` in `asr/editing.py` (Ollama `qwen3.5:9b`, self-correction) | partial; README records accuracy/latency gate open |
| Intent schema | `intent/schema.json` (fields: `intent_type` research/navigate/draft/prepare/execute/cancel/clarify, `goal`, `entities`, `constraints`, `prohibited_actions` send/submit/publish/purchase/delete/change_settings, `requires_approval`, `confidence`, `needs_clarification`, `clarifying_question`); validator `intent/validation.py` | tested |
| Intent compiler | `Compiler(model, editor=...).compile(raw) -> Compilation(normalized_command, structured_intent, decision, source, notice, latency_ms, model_valid)` in `intent/compiler.py`; model `OllamaModel("qwen2.5:3b")` in `intent/model.py` | tested (live model path requires Ollama) |
| Negation extraction | `intent/fallback.restrictions(text) -> (constraints, prohibited_actions)` (deterministic) | tested |
| Deterministic policy | `policy/engine.evaluate(command, intent) -> Decision(status, message)`; statuses `ready / approval_required / clarify / cancelled` | tested (file has uncommitted edits) |
| Approval / cancellation | `Session.prepare_tool / run_tool / cancel` in `session.py`: single-use token, `hmac.compare_digest`, 120-180 s expiry, invalidated by correction/cancel/restart | tested, but in-memory and **single-user** (no owner binding, no payload hash) |
| TTS | None. `voice.js` plays an oscillator chime only | planned/absent |
| Event logging | `storage/metrics.py` `VoiceMetrics` (SQLite `.runtime/voice/metrics.sqlite3`); `storage/audit.py` `ExecutionAudit` (SQLite, untracked file) | tested |
| MCP adapter | `aside/adapter.py` `MCPAdapter` (mock + real Aside), `aside/browser.py` | tested but untracked; **not used by MARCH** (Aside is gated off) |
| Speaker identification | — | absent (MARCH adds it) |

## Tests (real run)

```
cd ~/november-1 && .venv/bin/pytest -q --ignore=tests/user_flows -p no:cacheprovider
413 passed in 16.68s
```

`tests/user_flows` (Playwright browser flows) was skipped as not quick. This run covered the working tree, including uncommitted changes.

## Local runtime state

- Voice models are present in `.runtime/voice`: `small.en`, `base.en`, `silero_vad.onnx`, KWS zipformer, `keywords.txt`.
- Ollama models are present in `.runtime/models`: `qwen2.5:3b`, `qwen3.5:9b`, `qwen3:4b`, `qwen3:4b-instruct-2507-q4_K_M`, `qwen3:8b`, `qwen3.5:4b`, `gemma3:12b`.
- Ollama was **not running** at inspection, and there is no global `ollama` binary. Use `.runtime/ollama/ollama`.
- No November process was running. A Codex helper process has `november-1` as its working directory and was left alone.

## Intent fields MARCH consumes

| MARCH need | November field |
| --- | --- |
| Action type | `intent_type` plus policy `Decision.status` |
| Target / recipients | `entities` (policy grounds each entity in the command text) |
| Time range | No dedicated field. MARCH reads `constraints` and the normalized command deterministically for fixture slots. |
| Constraints / negations | `constraints`, `prohibited_actions` (also re-derived by `restrictions()`) |
| Clarification | `needs_clarification`, `clarifying_question` |

## Persistence to move to MongoDB

November keeps session history in memory and metrics/audit in SQLite. MARCH mirrors runs, pending actions, approvals and memories to Atlas. It does **not** delete or replace November's SQLite paths.

## How MARCH reuses it

- MARCH is a separate Python 3.13 package that imports `november` from the local checkout (`pip install -e ~/november-1` into MARCH's own venv). No files are copied.
- Typed input path: `Compiler.compile()` -> `Decision` -> MARCH scope, tools and pending actions.
- Voice path (M2): MARCH builds a `VoiceLoop` with November's detectors and `LocalWhisper`, wrapping the recognizer so ECAPA reads the same buffer. Submissions go to a MARCH session adapter.

## Blockers

1. `MONGODB_URI` is not set: MARCH has no `.env` yet.
2. Ollama must be started for the live compiler path. Cold-loading `qwen3.5:9b` is slow, and the editor timeout is 20 s.
3. SpeechBrain ECAPA is not installed. The model download is about 80 MB and lands in M2.
