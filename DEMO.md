# Demo runbook (about 60 seconds of video, about 5 minutes live)

Before you start: Ollama is running from `~/november-1/.runtime`, `.venv/bin/python -m march.server` is running, and http://127.0.0.1:8780 shows **Atlas ready** in green.

## 0. Setup, once
1. Enroll three volunteers: **Turn on microphone**, then **Enroll a consenting volunteer**, pick Asha, Ben or Casey, tick consent, and click **Start enrollment**. Hold Space for three clips of 8–10 s, then one verify sentence.
2. Calibrate: each person says 2 new commands and a non-enrolled person speaks twice. Then run `.venv/bin/python scripts/calibrate_voice.py emp_asha emp_asha emp_ben emp_ben emp_casey emp_casey unknown unknown`, and restart the server.
3. Optional: add `ELEVENLABS_API_KEY` (spoken acknowledgments) and `RAINDROP_WRITE_KEY` (traces) to `.env`, then restart.

## 1. Who is speaking -> private workspace
- "Asha" holds Space: *"find a 30 minute slot with Ben tomorrow"*. The page shows **Voice recognized: Asha** and her slots, in her timezone, from her calendar only.
- A non-enrolled person speaks. The page shows **"I don't recognize this voice"**, and nothing opens.

## 2. Memory changes behavior
- Asha: *"I prefer afternoon meetings"* -> *"Noted"*. Repeat the slot request: slots now start at 14:00.
- Ben: same request -> mornings. His workspace and memories are separate.

## 3. Exact-action approval
- Asha: *"email Priya about the launch plan"* -> a pending card. **Approve this exact email** -> SIMULATED send.
- *"draft an email to Ben about the budget, but do not send it"* -> draft only, and no approve button exists.

## 4. Web research (read-only)
- *"open https://example.com and summarize the page"* -> Aside opens and reads it, and the summary and source appear. Clicks and forms are refused by design.

## 5. Recursive harness, live (about 60 s)
1. Select **Casey** (manual selector or her voice) and scroll to the **Harness** card. The active version is **v1-baseline**. If it isn't, open **Versions** and click **Roll back to this** on v1.
2. Click **Run one improvement cycle**. The log streams live:
   - Baseline on 18 dev+val cases, 3 paired repeats: **0.889**. Casey's 25-minute meeting default was missed once her history grew (cases c03, c07).
   - Structural evidence the optimizer receives: `explicit_preference_existed_but_unused:scheduling.default_duration_minutes`.
   - The local optimizer proposes ONE allowlisted patch: `pinExplicitPreferences=true`.
   - The candidate is evaluated on the same cases: **1.000**. Gates: no critical failures, gain above the noise band, no regressions, at least one case fixed.
   - **Promoted** with compare-and-set. Only Casey changes; Asha and Ben stay on v1.
3. Point at "held-out test (never shown to optimizer)" and "Per-case failures" to show it was measured, not claimed.
4. Show safety: the optimizer cannot change scope, approvals, evaluators or expected outcomes (`march/harness.py` ALLOWLIST).
5. To repeat the demo: Versions → **Roll back to this** on v1, then run it again.

## Say in the video
"Voice-to-intent and the browser adapter are reused from my earlier NovemberAI project. Everything else (speaker routing, per-employee Atlas workspaces, memory, approvals and the self-improving harness) was built today."
