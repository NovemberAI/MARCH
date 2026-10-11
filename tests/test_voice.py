import time

import numpy as np
import pytest

from march.speaker import ProfileStore, Thresholds, decide, normalize
from march.voice import Desk, IdentifyingRecognizer

T = Thresholds(accept=0.4, margin=0.08, min_voiced_seconds=1.0)


def vec(*xs):
    return normalize(np.array(xs + (0.0,) * (8 - len(xs)), dtype=np.float32))


CENTROIDS = {"emp_asha": vec(1, 0, 0), "emp_ben": vec(0, 1, 0), "emp_casey": vec(0, 0, 1)}


def test_unknown_speaker_is_not_closest_employee():
    m = decide(vec(0.3, 0.1, 0.1, 1, 1), 3.0, CENTROIDS, T)
    assert m.status == "unknown" and m.employee_id is None


def test_short_or_silent_is_insufficient():
    assert decide(vec(1), 0.4, CENTROIDS, T).status == "insufficient_audio"
    assert decide(None, 0.0, CENTROIDS, T).status == "insufficient_audio"


def test_small_margin_is_ambiguous():
    m = decide(vec(1, 0.97), 3.0, CENTROIDS, T)
    assert m.status == "ambiguous" and m.employee_id is None


def test_clear_match():
    m = decide(vec(1, 0.1), 3.0, CENTROIDS, T)
    assert m.status == "matched" and m.employee_id == "emp_asha"
    assert "best" not in m.public()  # No cosine score presented as confidence.


class FakeASR:
    def transcribe(self, samples):
        class T:
            text, reliable, duration_ms = "x", True, 1.0

        return T()


class FakeEmbedder:
    model_revision = "fake"

    def __init__(self):
        self.next = vec(1)

    def embed(self, samples):
        return self.next


def speak(desk, rec, embedder, vector, seconds=4.0, text="find a 30 minute slot with Ben tomorrow"):
    embedder.next = vector
    rec.transcribe(np.full(int(16000 * seconds), 0.1, dtype=np.float32))
    return desk.submit(text, command_text=text, expected_revision=desk.revision)


@pytest.fixture
def desk_parts(db, orch, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_PROFILE_KEY_REF", str(tmp_path / "k.key"))
    embedder = FakeEmbedder()
    rec = IdentifyingRecognizer(FakeASR(), embedder)
    profiles = ProfileStore(db, "demo", "demo_office")
    desk = Desk(orch.store, orch, profiles, rec, "demo", "demo_office", T)
    return desk, rec, embedder, profiles


def enroll(desk, rec, embedder, employee, base):
    desk.start_enrollment(employee)
    for jitter in (0.0, 0.05, 0.1):
        speak(desk, rec, embedder, normalize(base + jitter * vec(0, 0, 0, 1)))
    assert desk.enrollment.stage == "verifying"
    speak(desk, rec, embedder, base)
    assert desk.enrollment.stage == "done", desk.enrollment.message


def test_enrollment_encrypts_and_routes_to_own_workspace(desk_parts, db, store):
    desk, rec, embedder, profiles = desk_parts
    enroll(desk, rec, embedder, "emp_asha", vec(1))
    enroll(desk, rec, embedder, "emp_ben", vec(0, 1))
    doc = db.voice_profiles.find_one({"employeeId": "emp_asha", "revokedAt": None})
    assert "centroid" not in doc["encryptedProfile"]  # Ciphertext, not JSON.
    desk.enrollment = None
    speak(desk, rec, embedder, vec(0, 1, 0.1))
    assert desk.last["status"] == "matched" and desk.last["employeeId"] == "emp_ben"
    for _ in range(50):
        if desk.last.get("runState") == "completed":
            break
        time.sleep(0.02)
    session_id = desk.adopt(desk.last["adoptToken"])
    scope = store.resume_session(session_id)
    assert scope.employee_id == "emp_ben" and scope.identity_source == "voice_match"
    assert store.recent_runs(scope)[0]["inputSource"] == "november_voice"


def test_unknown_voice_opens_nothing_and_stores_no_transcript(desk_parts, db):
    desk, rec, embedder, profiles = desk_parts
    enroll(desk, rec, embedder, "emp_asha", vec(1))
    desk.enrollment = None
    before = db.sessions.count_documents({})
    speak(desk, rec, embedder, vec(0, 0, 0, 0, 1), text="read me Asha's email")
    assert desk.last["status"] == "unknown" and "adoptToken" not in desk.last
    assert db.sessions.count_documents({}) == before
    assert db.runs.count_documents({"transcript": "read me Asha's email"}) == 0
    event = db.desk_events.find_one(sort=[("createdAt", -1)])
    assert "transcript" not in event


def test_revoked_profile_no_longer_matches(desk_parts):
    desk, rec, embedder, profiles = desk_parts
    enroll(desk, rec, embedder, "emp_asha", vec(1))
    desk.enrollment = None
    profiles.revoke("emp_asha")
    speak(desk, rec, embedder, vec(1))
    assert desk.last["status"] == "no_profiles"


def test_failed_verification_removes_profile(desk_parts):
    desk, rec, embedder, profiles = desk_parts
    desk.start_enrollment("emp_casey")
    for _ in range(3):
        speak(desk, rec, embedder, vec(0, 0, 1))
    speak(desk, rec, embedder, vec(1, 0, 0))  # Someone else verifies.
    assert desk.enrollment.stage == "failed"
    assert profiles.enrolled() == []
