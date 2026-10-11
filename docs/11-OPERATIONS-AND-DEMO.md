# 11. Operations, demo, and submission

## Local run (to be filled in with real commands by the coding agent)

1. Start NovemberAI the way `NOVEMBER-REUSE-MAP.md` records.
2. Start the MARCH app (local or hosted).
3. Start the bridge/speaker-ID process if separate.
4. Run seed and index scripts against `march_demo` and `march_eval` only.
5. Open the desk UI; confirm `/health` shows Atlas, November bridge, voice profiles, and optional integrations.

Reset: the reseed script may drop and recreate only `march_demo` and `march_eval`, after an explicit confirmation flag. It must refuse any other database name.

## Pre-demo checklist

- Three volunteers enrolled; calibration log written; thresholds frozen.
- Baseline harness active for all three fictional employees.
- Asha's afternoon preference stored before the baseline run.
- One non-enrolled person available to show the unknown-speaker state.
- Demo/live badge shows DEMO; all tool results labeled simulated.
- No secrets visible in UI, terminal, or browser tabs on screen.
- Raindrop/ElevenLabs/Modelence states accurate (or hidden if not used).

## 60-second demo script

- **0-8s:** "MARCH is one desk assistant that knows which of three coworkers is talking and keeps a private, self-improving workspace for each. Voice-to-intent is our existing NovemberAI; everything else was built today on MongoDB Atlas."
- **8-22s:** Asha asks for a meeting slot. UI shows "Asha" matched, proposal respects her stored afternoon preference... or, in the baseline, misses it.
- **22-32s:** Ben asks the same thing; different identity, different result from his own context. A non-enrolled voice gets "I don't recognize you".
- **32-50s:** Show the recorded failure, the one-line harness patch, the evaluation counts (baseline vs candidate, zero isolation failures), and promoted/rejected status. Optional Raindrop trace view.
- **50-60s:** Asha asks again; new version applies. Close: "Separate memory, separate tools, shared assistant, and a harness that only changes when the tests say it got better."

Record from the real running system. If any step falls back (manual identity, lexical retrieval, preliminary evaluation), the on-screen label stays visible.

## Live 3-minute judging version

Same flow, plus: enrollment of one person live (if time), "forget that" memory control, and a cross-employee request being refused. Prepare answers for: How do you stop one employee seeing another's data? What exactly changed in the harness? How do you know it improved? What happens if voice ID is wrong?

## Submission checklist (user performs)

- Repository in the November organization is **public**; NovemberAI dependency is accessible or clearly linked.
- README has built-before / built-during sections, setup steps, partner products used, and limitations.
- Secret scan of the repository (no `.env`, URIs, keys, tokens, voice data).
- Demo video plays with audio and is accessible by link.
- Project built in the event Atlas sandbox.
- All team members added on Cerebral Valley.
- Submit by 5:00 PM Pacific.

The coding agent prepares everything but does not publish, submit, or change repository visibility.
