"""Replay WAV files through the running server's November push-to-talk protocol (no mic).

Pipeline check only: synthetic or recorded clips stand in for a live microphone. Results from
synthetic voices are not evidence of real-speaker accuracy.

usage: replay_voice.py BASE_URL enroll EMPLOYEE clip1.wav clip2.wav clip3.wav verify.wav
       replay_voice.py BASE_URL speak clip.wav [clip.wav ...]
"""

import json
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import soundfile as sf

FRAME = 1280


def call(base: str, path: str, body: dict | None = None, frame: bytes | None = None,
         headers: dict | None = None) -> dict:
    data = frame if frame is not None else json.dumps(body or {}).encode()
    req = urllib.request.Request(base + path, data=data, method="POST", headers={
        "Content-Type": "application/octet-stream" if frame is not None else "application/json",
        **(headers or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"  {path} -> {exc.code} {exc.read()[:200]!r}")
        raise


def status(base: str) -> dict:
    with urllib.request.urlopen(base + "/api/voice/status", timeout=10) as resp:
        return json.loads(resp.read())


def say(base: str, path: str, capture: dict) -> dict:
    audio, rate = sf.read(path, dtype="float32")
    assert rate == 16000, "16 kHz mono WAV expected"
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    pcm = np.concatenate([pcm, np.zeros(FRAME * 4, dtype="<i2")])
    before = status(base)["desk"]["last"]
    for _ in range(40):  # November rejects a new capture while the previous one finishes.
        try:
            hold = call(base, "/api/voice/hold/start")
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise
            time.sleep(0.25)
    for i in range(0, len(pcm) - FRAME + 1, FRAME):
        call(base, "/api/voice/frame", frame=pcm[i:i + FRAME].tobytes(), headers={
            "X-Capture-Id": capture["capture_id"], "X-Audio-Sequence": str(capture["seq"])})
        capture["seq"] += 1
    call(base, "/api/voice/finish",
         {"capture_id": capture["capture_id"], "wake_count": hold["wake_count"]})
    quiet = np.zeros(FRAME, dtype="<i2").tobytes()
    for _ in range(240):
        # A live browser keeps streaming; silence keeps November's capture lease alive.
        call(base, "/api/voice/frame", frame=quiet, headers={
            "X-Capture-Id": capture["capture_id"], "X-Audio-Sequence": str(capture["seq"])})
        capture["seq"] += 1
        st = status(base)
        if st["state"] == "armed" and not st.get("busy") and st["desk"]["last"] != before:
            return st
        if st["state"] == "armed" and st["message"].startswith(("I couldn", "What would")):
            return st
        time.sleep(0.08)
    return status(base)


def main() -> None:
    base, verb, *rest = sys.argv[1:]
    start = call(base, "/api/voice/start")
    capture = {"capture_id": start["capture_id"], "seq": 0}
    try:
        if verb == "enroll":
            employee, *clips = rest
            call(base, "/api/enroll/start", {"fixtureEmployeeId": employee, "consent": True})
            for clip in clips:
                st = say(base, clip, capture)
                print(clip.rsplit("/", 1)[-1], "->", st["desk"]["enrollment"]["stage"],
                      "|", st["desk"]["enrollment"]["message"])
            call(base, "/api/enroll/cancel")
        else:
            for clip in rest:
                st = say(base, clip, capture)
                last = st["desk"]["last"]
                print(clip.rsplit("/", 1)[-1], "->", last.get("status"), last.get("employeeId"),
                      "| asr:", repr(st.get("transcript")), "|", last.get("diagnostics", {}))
    finally:
        call(base, "/api/voice/stop")


if __name__ == "__main__":
    main()
