# 13. NovemberAI reuse contract

## Decision

MARCH must reuse the user's existing NovemberAI code and architecture for speech capture, ASR, transcript checks, structured intent compilation and deterministic policy. Do not write a second ASR pipeline, a second intent parser, or a new prompt-only classifier for the same job.

The user owns NovemberAI and will place MARCH in the November GitHub organization. The coding agent must not create the organization, change its visibility, transfer repositories, or push without explicit user instruction.

## What is known and what is not

The recovered NovemberAI plans describe this staged design:

- Phase 1: text-only intent compiler producing strict schema-validated JSON, preserving negations such as "do not send" and "do not submit". A deterministic policy layer, not the model, classifies intents as safe, approval-required, unsupported, or needing clarification. Qwen2.5 3B Instruct through Ollama or llama.cpp was the initial candidate.
- Phase 2: microphone -> VAD -> wake word -> recording -> local ASR -> transcript checks -> intent compiler. Suggested defaults were openWakeWord or Porcupine, Silero or WebRTC VAD, faster-whisper or whisper.cpp, and SQLite for event and latency metrics.
- Phase 3: allowlisted Aside MCP tool registry, validation, dry-run mode, approval tokens, secret-free audit events, cancellation and timeouts, with a mock adapter if the real connection is unavailable.

These are planning records. The actual repository, language, implemented phases, module names, and current test status have not been inspected for this package. Treat the local checkout as the source of truth.

## First 15 minutes: build the reuse map

Before writing MARCH code, inspect the NovemberAI checkout and create `NOVEMBER-REUSE-MAP.md` with:

1. Repository path and current commit, plus whether uncommitted changes exist. Do not modify or reset them.
2. Runtime language and version, package manager, lock files, and launch command.
3. Exact entry points for: audio capture, VAD, wake word, ASR, transcript normalization/checks, intent schema, intent compiler, policy classifier, approval flow, cancellation, TTS, event logging, and MCP adapter.
4. Which of these are implemented and tested, partial, or only planned. Run existing tests if cheap; record actual results.
5. Intent schema fields relevant to MARCH: action type, target app, recipients, time range, constraints/negations, clarification flags.
6. Current persistence (for example SQLite) and which data MARCH must move to MongoDB.
7. Blockers: missing model weights, unavailable Ollama, microphone permissions, long downloads.

If Phase 2 voice code does not exist yet, stop and tell the user. Do not silently substitute a new ASR stack and call it reuse. The only acceptable fallback for the demo is the existing Phase 1 text compiler plus a clearly labeled typed-input path, unless the user approves an ASR choice.

## Integration seam

```text
[existing November capture + ASR + transcript checks]
        -> transcript, utteranceId, capture audio reference (in memory)
[NEW: MARCH speaker identification on the same captured audio]
        -> VoiceMatch (matched / unknown / ambiguous / insufficient)
[existing November intent compiler + deterministic policy]
        -> validated intent JSON + policy decision
[NEW: MARCH scope resolver, MongoDB memory, harness config, scoped tools]
        -> result, pending action, run record
[existing November approval / cancellation / TTS, extended with owner binding]
```

Rules:

- Speaker identification consumes the exact audio buffer November already captured. Do not open a second microphone stream.
- MARCH may add employee context to the intent compiler's input only through an explicit, schema-validated context field. Do not rewrite November's system prompt wholesale. If the compiler cannot accept context, run MARCH personalization after compilation.
- November's deterministic policy remains the first gate. MARCH adds owner binding, tenant scope, and payload-hash approval on top; it never loosens November's policy.
- November negation and constraint fields must survive into MARCH pending actions and the dispatcher.
- Keep November's existing event log. Mirror MARCH-relevant events to MongoDB; do not delete the SQLite path unless the user approves.

## Where MARCH code lives

Preferred: a new public `march` repository in the November organization, with NovemberAI included as a pinned dependency, git submodule, or local package path, so the hackathon submission can show exactly what was built today. The user decides which.

Acceptable when time is short: a clearly separated `march/` directory or branch inside the NovemberAI repository, if the user is comfortable making that repository public for submission.

Either way, never copy NovemberAI files into MARCH and present them as new.

## Event disclosure requirement

The event guide requires that judges can clearly identify what was built during the hackathon and disqualifies presenting an existing project as new work. Therefore:

- The MARCH README must contain a "Built before the event" section naming NovemberAI ASR, intent compiler, policy and any reused UI, with a link and commit.
- A "Built during the event" section lists speaker identification, per-employee MongoDB context, scoped tools, approval owner binding, harness versioning and evaluation, Modelence/Raindrop/ElevenLabs integrations, and the demo UI.
- Git history should show MARCH commits made today. Do not squash NovemberAI history into MARCH.
- The 60-second video and live demo focus on the new MARCH features and say in one sentence that voice-to-intent is reused from NovemberAI.

## Runtime placement

- If NovemberAI is Node.js or TypeScript: import its modules directly into the MARCH service where feasible; one Modelence service is then plausible.
- If NovemberAI is Python: keep it running locally as-is. Add only an outbound bridge client that posts authenticated events to the hosted MARCH app. Modelence's documented deploy runtime is Node.js only, so the Python voice stack is not deployed there. See [partner products](14-PARTNER-PRODUCTS.md).
- If neither bridge nor hosting works within the time box: run everything locally, use the event Atlas sandbox directly, and mark hosted deployment as deferred.
