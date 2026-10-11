"""Glue between NovemberAI's VoiceLoop and MARCH. November captures and transcribes; MARCH
identifies the speaker on that same buffer and routes to the matched employee's workspace."""

import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from march.db import Store, new_id, now
from march.orchestrator import Orchestrator
from march.speaker import (
    Embedder,
    ProfileStore,
    Thresholds,
    VoiceMatch,
    consistency,
    decide,
    load_thresholds,
    voiced_seconds,
)

ENROLL_CLIPS = 3
ENROLL_MIN_VOICED = 3.0
ENROLL_MIN_CONSISTENCY = 0.35

UNKNOWN_MESSAGES = {
    "unknown": "I don't recognize this voice, so I haven't opened anyone's workspace.",
    "ambiguous": "I couldn't tell who that was. Please say it again on your own.",
    "insufficient_audio": "That was too short for me to recognize your voice. Please say a bit more.",
    "no_profiles": "No one has enrolled a voice yet.",
}


@dataclass
class Enrollment:
    employee_id: str
    embeddings: list[Any] = field(default_factory=list)
    stage: str = "collecting"  # collecting | verifying | done | failed
    message: str = ""


class IdentifyingRecognizer:
    """Implements November's SpeechRecognizer protocol. Delegates text to November's ASR and
    embeds the identical buffer; no second microphone stream exists."""

    def __init__(self, asr: Any, embedder: Embedder) -> None:
        self.asr = asr
        self.embedder = embedder
        self.local = threading.local()

    def transcribe(self, samples: Any) -> Any:
        transcript = self.asr.transcribe(samples)
        voiced = voiced_seconds(samples)
        embedding = self.embedder.embed(samples) if voiced >= 0.5 else None
        self.local.last = (embedding, voiced)
        return transcript

    def take_last(self) -> tuple[Any, float]:
        last = getattr(self.local, "last", (None, 0.0))
        self.local.last = (None, 0.0)
        return last


class Desk:
    """Plays the role of November's Session for VoiceLoop: snapshot(), submit(), cancel()."""

    def __init__(
        self,
        store: Store,
        orch: Orchestrator,
        profiles: ProfileStore,
        recognizer: IdentifyingRecognizer,
        mode: str,
        org_id: str,
        thresholds: Thresholds | None = None,
    ) -> None:
        self.store, self.orch, self.profiles, self.recognizer = store, orch, profiles, recognizer
        self.mode, self.org_id = mode, org_id
        self.thresholds = thresholds or load_thresholds()
        self.revision = 0
        self.lock = threading.RLock()
        self.enrollment: Enrollment | None = None
        self.last: dict[str, Any] = {"status": "idle"}
        self.adopt_tokens: dict[str, str] = {}

    # --- November Session protocol subset ---
    def snapshot(self) -> dict[str, Any]:
        return {"revision": self.revision}

    def cancel(self) -> dict[str, Any]:
        with self.lock:
            self.revision += 1
            self.last = {"status": "cancelled", "message": "Cancelled. Nothing was carried out."}
        return self.snapshot()

    def clear(self) -> dict[str, Any]:
        return self.cancel()

    def submit(
        self, raw: str, *, command_text: str | None = None, expected_revision: int | None = None
    ) -> dict[str, Any]:
        embedding, voiced = self.recognizer.take_last()
        command = command_text or raw
        with self.lock:
            self.revision += 1
            utterance = new_id()
            if self.enrollment and self.enrollment.stage in {"collecting", "verifying"}:
                self._enroll_clip(embedding, voiced)
                return {"current": {"id": utterance, "revision": self.revision}}
            match = decide(embedding, voiced, self.profiles.centroids(), self.thresholds)
            self._route(utterance, command, match)
            return {"current": {"id": utterance, "revision": self.revision}}

    # --- enrollment ---
    def start_enrollment(self, employee_id: str) -> dict[str, Any]:
        with self.lock:
            self.enrollment = Enrollment(
                employee_id, message=f"Clip 1 of {ENROLL_CLIPS}: hold the talk button and speak "
                "naturally for about 8-10 seconds."
            )
            return self.status()

    def cancel_enrollment(self) -> dict[str, Any]:
        with self.lock:
            self.enrollment = None
            return self.status()

    def _enroll_clip(self, embedding: Any, voiced: float) -> None:
        e = self.enrollment
        assert e is not None
        if embedding is None or voiced < (ENROLL_MIN_VOICED if e.stage == "collecting" else 1.0):
            e.message = f"That clip had {voiced:.1f}s of speech; please speak a little longer."
            return
        if e.stage == "collecting":
            e.embeddings.append(embedding)
            if len(e.embeddings) < ENROLL_CLIPS:
                e.message = (
                    f"Clip {len(e.embeddings) + 1} of {ENROLL_CLIPS}: say a different sentence."
                )
                return
            worst = consistency(e.embeddings)
            if worst < ENROLL_MIN_CONSISTENCY:
                e.embeddings.clear()
                e.message = (
                    f"Those clips were not consistent (min similarity {worst:.2f}). "
                    "Let's re-record all three in a quieter spot."
                )
                return
            self.profiles.save(e.employee_id, e.embeddings, self.recognizer.embedder.model_revision)
            e.embeddings = []  # Do not keep raw embeddings around after persistence.
            e.stage = "verifying"
            e.message = "Saved. Now say one new sentence so I can check that I recognize you."
            return
        match = decide(embedding, voiced, self.profiles.centroids(), self.thresholds)
        if match.status == "matched" and match.employee_id == e.employee_id:
            e.stage = "done"
            e.message = "Enrollment verified: I recognized your new sentence."
        else:
            self.profiles.revoke(e.employee_id)
            e.stage = "failed"
            e.message = (
                f"Verification failed ({match.status}); the profile was removed. Please re-enroll."
            )
        self.last = {"status": "enrollment", "diagnostics": match.diagnostics()}

    # --- routing ---
    def _route(self, utterance: str, command: str, match: VoiceMatch) -> None:
        self.store.db.desk_events.insert_one(
            {
                "_id": utterance,
                "mode": self.mode,
                "orgId": self.org_id,
                "kind": "voice_identification",
                "status": match.status,
                "matchedEmployeeId": match.employee_id,
                "diagnostics": match.diagnostics(),
                "thresholdsCalibrated": self.thresholds.calibrated,
                "createdAt": now(),
            }
        )
        if match.status != "matched" or match.employee_id is None:
            # Unknown means unknown: no workspace opens and no transcript is stored anywhere.
            self.last = {
                "status": match.status,
                "message": UNKNOWN_MESSAGES[match.status],
                "diagnostics": match.diagnostics(),
                "utteranceId": utterance,
            }
            return
        scope = self.store.open_session(self.mode, self.org_id, match.employee_id, "voice_match")
        token = secrets.token_urlsafe(24)
        self.adopt_tokens[token] = scope.session_id
        self.last = {
            "status": "matched",
            "employeeId": match.employee_id,
            "message": "Recognized. Working on it…",
            "diagnostics": match.diagnostics(),
            "adoptToken": token,
            "utteranceId": utterance,
            "runState": "compiling",
        }
        revision = self.revision

        def work() -> None:
            run = self.orch.handle(scope, command, "november_voice", voice=match.diagnostics())
            with self.lock:
                if self.revision == revision:
                    self.last = {**self.last, "runState": run["state"], "runId": run["_id"]}

        threading.Thread(target=work, daemon=True, name="march-voice-run").start()

    def adopt(self, token: str) -> str | None:
        with self.lock:
            return self.adopt_tokens.pop(token, None)

    def status(self) -> dict[str, Any]:
        with self.lock:
            e = self.enrollment
            return {
                "last": {k: v for k, v in self.last.items() if k != "adoptToken"}
                | ({"adoptToken": self.last["adoptToken"]} if "adoptToken" in self.last else {}),
                "enrolled": self.profiles.enrolled(),
                "thresholds": {
                    "accept": self.thresholds.accept,
                    "margin": self.thresholds.margin,
                    "calibrated": self.thresholds.calibrated,
                },
                "enrollment": None
                if e is None
                else {
                    "employeeId": e.employee_id,
                    "stage": e.stage,
                    "clips": len(e.embeddings),
                    "message": e.message,
                },
            }


def build_voice(
    store: Store, orch: Orchestrator, mode: str, org_id: str
) -> tuple[Any, Desk]:
    """Construct November's VoiceLoop with November's own detectors and ASR, wrapped for ID."""
    from november.asr.local import LocalWhisper
    from november.audio.controller import VoiceLoop
    from november.audio import controller as november_controller
    from november.audio.detectors import (
        KWS_DIRECTORY,
        SherpaWakeWordDetector,
        SileroVoiceActivityDetector,
    )
    from november.storage.metrics import VoiceMetrics

    from march.speaker import RUNTIME, EcapaEmbedder

    root = Path(
        os.getenv("NOVEMBER_VOICE_MODELS", "/Users/shashwatraj/november-1/.runtime/voice")
    )
    name = os.getenv("NOVEMBER_ASR_MODEL", "small.en")
    kws_root = march_wake_root(root, KWS_DIRECTORY)
    # November's transcript-side wake check is a module constant; MARCH swaps the phrase only.
    november_controller.WAKE_PREFIX = WAKE_PREFIX
    recognizer = IdentifyingRecognizer(LocalWhisper(root / name), EcapaEmbedder())
    desk = Desk(store, orch, ProfileStore(store.db, mode, org_id), recognizer, mode, org_id)
    loop = VoiceLoop(
        desk,  # type: ignore[arg-type]  # Duck-typed Session: snapshot/submit/cancel/clear.
        SherpaWakeWordDetector(kws_root),
        SileroVoiceActivityDetector(root),
        recognizer,
        VoiceMetrics(RUNTIME / "voice-metrics.sqlite3"),
    )
    return loop, desk


WAKE_PHRASE = "Hey March"
WAKE_PREFIX = re.compile(r"^\s*hey[,! .]*march\b[,! .:]*", re.I)


def march_wake_root(november_root: Path, kws_directory: str) -> Path:
    """A MARCH-owned keywords dir: November's KWS model (symlinked, unmodified) + 'HEY MARCH'.
    The internal label stays HEY_NOVEMBER because November's VoiceLoop matches on it."""
    import sentencepiece as spm

    from march.speaker import RUNTIME

    out = RUNTIME / "voice_kws"
    out.mkdir(parents=True, exist_ok=True)
    link = out / kws_directory
    if not link.exists():
        link.symlink_to(november_root / kws_directory, target_is_directory=True)
    tokenizer = spm.SentencePieceProcessor(model_file=str(link / "bpe.model"))
    lines = [
        " ".join(tokenizer.encode("HEY MARCH", out_type=str)) + " @HEY_NOVEMBER",
        " ".join(tokenizer.encode("CANCEL", out_type=str)) + " @CANCEL",
    ]
    (out / "keywords.txt").write_text("\n".join(lines) + "\n")
    return out


def wake_text(message: str) -> str:
    return message.replace("Hey November", WAKE_PHRASE).replace("restart November", "restart MARCH")


def silence(seconds: float) -> Any:
    return np.zeros(int(16000 * seconds), dtype=np.float32)
