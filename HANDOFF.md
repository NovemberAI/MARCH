# HANDOFF (for the next model/session)

Read `AGENTS.md`, then this file, then `IMPLEMENTATION-STATUS.md` and `NOVEMBER-REUSE-MAP.md`.

## Current state (2026-10-11 ~15:15 PDT)

- M0 and M1 are done and **persisted in the event Atlas sandbox**. `.env` holds `MONGODB_URI`; it is local only, gitignored and chmod 600, and must never be printed or committed. The user will delete the Atlas user after the event.
- NovemberAI lives at `/Users/shashwatraj/november-1`. Never modify it. It is importable in MARCH's venv through `.venv/lib/python3.13/site-packages/november_local_checkout.pth`, which points at `~/november-1/src`.
- Ollama, needed for the live November compiler, is started from November's runtime: `cd ~/november-1 && OLLAMA_MODELS="$PWD/.runtime/models" OLLAMA_NO_CLOUD=1 .runtime/ollama/ollama serve`. Check with `curl localhost:11434/api/version` before starting a second copy.
- MARCH server: `.venv/bin/python -m march.server` on port 8780. Check whether one is already running before launching another.
- Nothing is committed yet. The user has not asked for commits or pushes.

## Layout

- `march/config.py`: env settings; live mode refused.
- `march/scope.py`: frozen `RequestScope`, built only by the server.
- `march/db.py`: `Store`, the scoped repository. Every method takes a scope, and `stamp()` overwrites scope fields.
- `march/november_bridge.py`: calls November's `Compiler` exactly as November's CLI does; `MARCH_COMPILER=offline` selects November's diagnostic grammar, which only covers a few commands.
- `march/tools.py`: `route()` maps November intent to a capability; fixture `find_slots` and `prepare_mail` read only the caller's own fixture items.
- `march/actions.py`: payload hash, compare-and-set approve/reject/edit, simulated send.
- `march/orchestrator.py`: one request -> run doc; `BASELINE_CONFIG` holds the harness knobs that M4 will version.
- `march/memory.py`: `active_preferences`, an indexed read-your-writes path.
- `march/server.py`, `march/ui/index.html`: stdlib HTTP server and a single-page UI.
- `tests/`: 20 tests (isolation, approval, voice).
- `.venv/.../march_local.pth` makes `march` importable for scripts.

## Next steps

1. (Done: Atlas connected; both DBs seeded.)
2. M2 is DONE in code: `march/speaker.py` (ECAPA, decide(), encrypted ProfileStore with key in `.runtime/voice_profile.key`), `march/voice.py` (IdentifyingRecognizer wraps November `LocalWhisper`; Desk is a duck-typed November Session; build_voice constructs November `VoiceLoop` with November detectors). Server serves November's `audio-worklet.js` unmodified; routes `/api/voice/*` and `/api/enroll/*`. REMAINING: the user enrolls 3 real volunteers in the UI, then runs the calibration in `scripts/calibrate_voice.py` and restarts. Replay tool: `scripts/replay_voice.py` (keeps sending silence frames because November's 3 s watchdog drops idle captures). Old note: wrap November's `SpeechRecognizer` (`LocalWhisper`) so SpeechBrain ECAPA reads the same buffer in `VoiceLoop._transcribe`. Build `VoiceLoop` with November's detectors and a MARCH session adapter exposing `.submit(raw, command_text=..., expected_revision=...)`. Decisions: matched/unknown/ambiguous/insufficient. Profiles go in `voice_profiles`, encrypted.
3. M3 is DONE: `march/memory.py` (typed preference extractor, commit/supersede, forget+tombstone, `recall()` using Atlas `$vectorSearch` with `query.text` on the autoEmbed index, rehydrated through a scoped find, lexical fallback). Old note: preference write path ("remember I prefer afternoons"), forget, and Vector Search autoEmbed.
4. M4: `harness_versions`, eval cases with **cached real November compilations**, an optimizer patch over the `BASELINE_CONFIG` allowlist, and gates.

## Gotchas

- A live November compile takes 15-26 s warm, mostly the 9b editor. Evals should compile each transcript once and cache the result.
- November's policy returns `approval_required` for "email X". MARCH routes on top of that and never loosens it.
- `route()` keywords are capability routing over November's validated intent, not a second intent parser.
