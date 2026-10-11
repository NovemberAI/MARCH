"""Local speaker identification (SpeechBrain ECAPA) on the buffer November already captured.

Identification routes to fictional demo workspaces only. It never authorizes live access.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

import numpy as np
from cryptography.fernet import Fernet
from numpy.typing import NDArray

from march.config import ROOT
from march.db import SCHEMA_VERSION, new_id, now

MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
SAMPLE_RATE = 16000
RUNTIME = ROOT / ".runtime"
CALIBRATION_FILE = ROOT / "voice_calibration.json"

Vector = NDArray[np.float32]


@dataclass(frozen=True)
class Thresholds:
    accept: float = 0.40  # Provisional until calibrated; see voice_calibration.json.
    margin: float = 0.08
    min_voiced_seconds: float = 1.0
    calibrated: bool = False


def load_thresholds() -> Thresholds:
    if CALIBRATION_FILE.is_file():
        data = json.loads(CALIBRATION_FILE.read_text())
        return Thresholds(
            float(data["accept"]),
            float(data["margin"]),
            float(data.get("min_voiced_seconds", 1.0)),
            True,
        )
    return Thresholds()


@dataclass(frozen=True)
class VoiceMatch:
    status: str  # matched | unknown | ambiguous | insufficient_audio | no_profiles
    employee_id: str | None
    best: float | None
    margin: float | None
    voiced_seconds: float
    scores: dict[str, float] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        """Labels only; raw cosine scores are development diagnostics, never 'confidence'."""
        return {"status": self.status, "employeeId": self.employee_id}

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "employeeId": self.employee_id,
            "best": None if self.best is None else round(self.best, 3),
            "margin": None if self.margin is None else round(self.margin, 3),
            "voicedSeconds": round(self.voiced_seconds, 2),
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
        }


def voiced_seconds(samples: Vector) -> float:
    """Energy-based voiced duration in 20 ms frames. A coarse gate, not an overlap detector."""
    frame = SAMPLE_RATE // 50
    usable = len(samples) // frame * frame
    if usable == 0:
        return 0.0
    rms = np.sqrt(np.mean(samples[:usable].reshape(-1, frame) ** 2, axis=1))
    return float(np.sum(rms > 0.01)) * 0.02


def decide(
    query: Vector | None,
    voiced: float,
    centroids: dict[str, Vector],
    thresholds: Thresholds,
) -> VoiceMatch:
    if voiced < thresholds.min_voiced_seconds or query is None:
        return VoiceMatch("insufficient_audio", None, None, None, voiced)
    if not centroids:
        return VoiceMatch("no_profiles", None, None, None, voiced)
    scores = {eid: float(np.dot(query, c)) for eid, c in centroids.items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_id, best = ranked[0]
    runner = ranked[1][1] if len(ranked) > 1 else -1.0
    margin = best - runner
    if best < thresholds.accept:
        return VoiceMatch("unknown", None, best, margin, voiced, scores)
    if margin < thresholds.margin:
        return VoiceMatch("ambiguous", None, best, margin, voiced, scores)
    return VoiceMatch("matched", best_id, best, margin, voiced, scores)


def normalize(vector: NDArray[Any]) -> Vector:
    v = np.asarray(vector, dtype=np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-9)


class Embedder(Protocol):
    model_revision: str

    def embed(self, samples: Vector) -> Vector: ...


class EcapaEmbedder:
    def __init__(self) -> None:
        from speechbrain.inference.speaker import EncoderClassifier

        self.model = EncoderClassifier.from_hparams(
            source=MODEL_ID,
            savedir=str(RUNTIME / "ecapa"),
            run_opts={"device": "cpu"},
        )
        self.model_revision = "hf-main-cached"
        self.lock = RLock()

    def embed(self, samples: Vector) -> Vector:
        import torch

        with self.lock, torch.no_grad():
            wav = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32)).unsqueeze(0)
            emb = self.model.encode_batch(wav).squeeze().cpu().numpy()
        return normalize(emb)


def _key() -> Fernet:
    """Profile key lives outside MongoDB in a local 0600 file (gitignored)."""
    path = Path(os.getenv("VOICE_PROFILE_KEY_REF") or RUNTIME / "voice_profile.key")
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
        path.chmod(0o600)
    return Fernet(path.read_bytes())


class ProfileStore:
    """Encrypted profiles in `voice_profiles`; decrypted centroids cached until revoke/restart."""

    def __init__(self, db: Any, mode: str, org_id: str) -> None:
        self.db, self.mode, self.org_id = db, mode, org_id
        self.fernet = _key()
        self.cache: dict[str, Vector] | None = None
        self.lock = RLock()

    def centroids(self) -> dict[str, Vector]:
        with self.lock:
            if self.cache is None:
                cache: dict[str, Vector] = {}
                for doc in self.db.voice_profiles.find(
                    {"mode": self.mode, "orgId": self.org_id, "revokedAt": None}
                ):
                    data = json.loads(self.fernet.decrypt(doc["encryptedProfile"].encode()))
                    cache[doc["employeeId"]] = normalize(np.array(data["centroid"]))
                self.cache = cache
            return dict(self.cache)

    def save(self, employee_id: str, embeddings: list[Vector], revision: str) -> dict[str, Any]:
        centroid = normalize(np.mean(np.stack(embeddings), axis=0))
        blob = json.dumps(
            {"centroid": centroid.tolist(), "samples": [e.tolist() for e in embeddings]}
        ).encode()
        scope = {"mode": self.mode, "orgId": self.org_id, "employeeId": employee_id}
        with self.lock:
            self.db.voice_profiles.update_many(
                {**scope, "revokedAt": None}, {"$set": {"revokedAt": now()}}
            )
            version = self.db.voice_profiles.count_documents(scope) + 1
            doc = {
                "_id": new_id(),
                "schemaVersion": SCHEMA_VERSION,
                **scope,
                "profileVersion": version,
                "modelId": MODEL_ID,
                "modelRevision": revision,
                "embeddingDimension": int(centroid.shape[0]),
                "sampleRateHz": SAMPLE_RATE,
                "encryptedProfile": self.fernet.encrypt(blob).decode(),
                "encryptionKeyRef": "local-file:.runtime/voice_profile.key",
                "enrollmentClipCount": len(embeddings),
                "revokedAt": None,
                "createdAt": now(),
            }
            self.db.voice_profiles.insert_one(doc)
            self.db.employees.update_one(
                scope,
                {
                    "$set": {
                        "activeVoiceProfileId": doc["_id"],
                        "consent.voiceEnrollment": True,
                        "consent.grantedAt": now(),
                        "consent.policyVersion": "demo-1",
                    }
                },
            )
            self.cache = None
        return {"profileId": doc["_id"], "profileVersion": version}

    def revoke(self, employee_id: str) -> int:
        scope = {"mode": self.mode, "orgId": self.org_id, "employeeId": employee_id}
        with self.lock:
            result = self.db.voice_profiles.update_many(
                {**scope, "revokedAt": None},
                {"$set": {"revokedAt": now(), "encryptedProfile": ""}},
            )
            self.db.employees.update_one(
                scope, {"$set": {"activeVoiceProfileId": None, "consent.voiceEnrollment": False}}
            )
            self.cache = None
        return result.modified_count

    def enrolled(self) -> list[str]:
        return sorted(self.centroids())


def consistency(embeddings: list[Vector]) -> float:
    """Minimum pairwise cosine among enrollment clips."""
    worst = 1.0
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            worst = min(worst, float(np.dot(embeddings[i], embeddings[j])))
    return worst
