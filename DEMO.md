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

## 5. Recursive harness (the main point)
- Select Casey, open the **Harness** card, and click **Run one improvement cycle**. Allow a few minutes because of embedding rate limits.
- The panel shows:
  - the optimizer's single allowlisted patch;
  - baseline vs candidate pass rates over 3 paired repeats;
  - the noise band;
  - fixed and regressed cases;
  - held-out test counts;
  - **promoted** or **rejected** with reasons.
- Real history is in `IMPLEMENTATION-STATUS.md` → "M4 cycles". Cycle 1 was an honest rejection.

## Say in the video
"Voice-to-intent and the browser adapter are reused from my earlier NovemberAI project. Everything else (speaker routing, per-employee Atlas workspaces, memory, approvals and the self-improving harness) was built today."
