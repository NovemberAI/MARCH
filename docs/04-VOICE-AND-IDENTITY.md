# 04. Voice and identity

## Distinguish the jobs

- Speech-to-text: what was said. Provided by NovemberAI's existing ASR; MARCH does not add another.
- Diarization: which anonymous speaker spoke when.
- Speaker identification: which enrolled person best matches the audio.
- Authentication: whether this request is allowed to access an account.

MARCH needs identification for three enrolled people. It does not need full meeting diarization for the MVP. Identification is probabilistic and vulnerable to replay, mimicry and synthetic speech; it must not be the sole live-account authentication factor.

## Enrollment flow

1. Operator explains the purpose, what is stored, local/cloud processing and how to revoke.
2. Participant explicitly consents and chooses a demo identity. For live enrollment, bind to an independently authenticated owner before capture.
3. Record three clean samples, initially targeting approximately 8-15 seconds each. Use different natural phrases; do not require secrets or personal details.
4. Decode each clip, convert to mono and resample to the model's expected rate. Initial ECAPA adapter uses 16 kHz audio, verified against its model configuration.
5. Reject clips that are too short, silent, badly clipped, corrupted or clearly contain multiple speakers. Do not claim a simple VAD reliably detects all overlaps.
6. Extract embeddings with the same frozen model/revision used at inference. L2-normalize. Retain several sample embeddings plus a normalized centroid rather than relying on a single utterance.
7. Check that enrollment samples are reasonably consistent; if not, ask for a clean recapture.
8. Encrypt the serialized profile, persist it with model version and consent reference, then test a previously unheard utterance.
9. Enrollment succeeds only after persistence and held-back-phrase verification, not after a progress animation.

Do not update a voice profile automatically from ordinary requests. Otherwise one mistaken match can contaminate the profile and reinforce future misidentification. Re-enrollment is an explicit owner-confirmed action.

## Audio capture contract

- Push-to-talk only initially; microphone is never silently left open.
- One speaker and one command per clip.
- Target 2-10 seconds of useful speech for ordinary commands. The minimum accepted voiced duration must be calibrated, not treated as universally sufficient.
- Proposed upload cap: 10 MB and 30 seconds. Validate decoded duration too, not only MIME metadata.
- Use browser-supported MediaRecorder formats, detected with `isTypeSupported`; common WebM/Opus needs a decoder.
- If FFmpeg is required, document and check installation rather than downloading an executable silently. A WAV capture route may be used instead.
- Keep speaker recognition local. Reuse NovemberAI's capture buffer; never open a second microphone stream.
- Do not record while assistant TTS is playing. Avoid the assistant recognizing its own output.
- Clear transient audio from memory/temp files after processing. Do not embed microphone data in exception traces or analytics.

## Identification algorithm

For normalized query embedding q and profile centroids c_i:

```text
score_i = cosine(q, c_i)
best = highest score
runner_up = second-highest score
margin = score_best - score_runner_up

accept only if:
  audio quality and voiced duration pass
  enrollment profile is active and not revoked
  score_best >= calibrated acceptance threshold
  margin >= calibrated separation margin
  no ambiguity/overlap warning requires rejection
otherwise return unknown, ambiguous, or insufficient_audio
```

The model's cosine score is not a calibrated probability. Never display 0.82 cosine as '82% certain'. Use labels such as matched, uncertain and unknown, with detailed numerical diagnostics restricted to the development view.

For three employees, compare locally against all three profiles. Do not use approximate nearest-neighbor retrieval or text embeddings for identity.

## Calibration protocol

- Keep enrollment clips separate from calibration and final-test clips.
- Collect new phrases from each enrolled speaker at realistic laptop distances.
- Include an opt-in fourth person's voice or licensed/consented unknown-speaker samples.
- Include background noise, very short speech and silence.
- Pick threshold and margin using the calibration set; freeze them before the final test.
- Measure confusion matrix, false accepts of unknown speakers, false rejections of enrolled speakers, and rejection coverage.
- Test at the actual venue and microphone. Do not extrapolate studio performance to a noisy room.
- If reliable thresholds cannot be found, mark voice identification blocked/reduced. Retain an explicitly labeled manual demo mode rather than hiding the failure.

Target zero unknown-to-enrolled false accepts in the small final demo set. This is a release criterion for that set, not a real-world guarantee. For sensitive data, independent account authentication remains required even if all sample tests pass.

## Binding identity to authorization

### Demo mode

A recognized consenting volunteer may select their assigned fictional workspace. A visible manual profile selector may be used for debugging only and must be labeled 'manual fixture identity'. Do not use that selector to fake a voice-recognition demonstration.

### Live mode

A voice match can suggest an identity, but private data stays locked until an independently authenticated employee authorizes the run from a personal surface. A phone/owner session or separate trusted personal browser can provide this binding. The shared desk screen should show only generic status and non-sensitive task handles until that authorization exists.

For the hackathon, if private approval infrastructure is not ready, restrict live operation to a single authenticated operator's personal session or leave live mode disabled. Do not load three real mailboxes into the shared kiosk and call it secure because the UI shows three names.

Every active task, pending action and approval retains its original owner. A later voice saying 'yes' cannot approve another person's action. Live write approval is an authenticated UI action, not just a spoken affirmation.

## Speaker switching

- Finish or pause the current capture before accepting another.
- Create/select the new employee's own session; never rename the previous one.
- Clear displayed private output before a new unauthenticated interaction.
- Invalidate only the desk's display binding, not the original task ownership.
- Keep the previous employee's pending action available only on their authorized surface.
- An ambiguous new clip does not inherit the last identity.

## Revocation

Revoke profile access immediately, erase its encrypted profile and cached decrypted copy, delete transient files, and cancel any unbound queued clips. Do not automatically erase all unrelated memories unless the owner asks; explain which deletion action is being performed. Complete account deletion is a separate broader flow.

Sources: [SpeechBrain ECAPA model](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb), [pyannote terminology](https://www.pyannote.ai/blog/speaker-diarization-vs-recognition-vs-identification). Verify library APIs against installed versions during implementation.
