"""Redacted Raindrop telemetry (evidence only; MongoDB stays the authority).

Sends allowlisted, non-content fields for runs and improvement-cycle evaluations to
Raindrop's HTTP ingest (`POST https://api.raindrop.ai/v1/events/track`, Bearer write key),
the same endpoint the official `raindrop-ai` Python SDK posts to. The SDK is not used because
it pulls OpenTelemetry/Traceloop into the venv; one HTTP POST is enough here.

Invariant 12: never transcripts, email payloads, memory text, web content/URLs, tokens,
Mongo URIs, voice scores or embeddings. Payloads are built from an allowlist, never by
copying and deleting. No-op when RAINDROP_WRITE_KEY is unset. Never raises into callers.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("march.telemetry")

API_URL = os.getenv("RAINDROP_API_URL", "https://api.raindrop.ai/v1/")
TIMEOUT_S = 3.0
_ID_CHARS = 64  # Run/version/case ids are opaque server ids; cap length defensively.


def _key() -> str | None:
    return os.environ.get("RAINDROP_WRITE_KEY") or None


def employee_hash(employee_id: Any) -> str:
    return hashlib.sha256(str(employee_id or "unknown").encode()).hexdigest()[:12]


def _s(value: Any) -> str | None:
    return None if value is None else str(value)[:_ID_CHARS]


def _num(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _latency_ms(run: dict[str, Any]) -> int | None:
    if run.get("latencyMs") is not None:
        return _num(run.get("latencyMs"))
    start, end = run.get("startedAt"), run.get("completedAt")
    if isinstance(start, datetime) and isinstance(end, datetime):
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return int((end - start).total_seconds() * 1000)
    return None


def _codes(values: Any) -> list[str]:
    """Failure codes are short machine labels; keep only the code part, never a message body."""
    if not isinstance(values, (list, tuple)):
        return []
    return [str(v).split(":", 1)[0][:_ID_CHARS] for v in values][:20]


def _clean(props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in props.items() if v is not None}


def redact_run(run: dict[str, Any], variant: str | None = None) -> dict[str, Any]:
    """Build the Raindrop event for a run from an allowlist of non-content fields."""
    voice = run.get("voice") if isinstance(run.get("voice"), dict) else {}
    result = run.get("result") if isinstance(run.get("result"), dict) else {}
    mode = _s(run.get("mode"))
    props = _clean({
        "runId": _s(run.get("_id")),
        "employeeHash": employee_hash(run.get("employeeId")),
        "mode": mode,
        "inputSource": _s(run.get("inputSource")),
        "identitySource": _s(run.get("identitySource")),
        "voiceStatus": _s(voice.get("status")) if voice else None,
        "capability": _s(run.get("capability")),
        "resultStatus": _s(result.get("status")),
        "state": _s(run.get("state")),
        "harnessVersionId": _s(run.get("harnessVersionId")),
        "harnessLabel": _s(run.get("harnessLabel")),
        "variant": variant or ("eval" if mode == "eval" else "live"),
        "recallMethod": _s(run.get("recallMethod")),
        "preferencesUsedCount": len(run.get("preferencesUsed") or []),
        "selectedMemoryCount": len(run.get("selectedMemoryIds") or []),
        "pendingActionCount": len(run.get("pendingActionIds") or []),
        "failureCodes": _codes(run.get("failureCodes")),
        "latencyMs": _latency_ms(run),
    })
    return {
        "event_id": props.get("runId"),
        "user_id": props["employeeHash"],
        "event": "march_run",
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "properties": props,
    }


def _split(stats: Any) -> dict[str, Any] | None:
    if not isinstance(stats, dict):
        return None
    return {"passed": _num(stats.get("passed")), "total": _num(stats.get("total"))}


def _rates(values: Any) -> list[float]:
    return [v for v in (values or []) if _num(v) is not None] if isinstance(values, list) else []


def redact_evaluation(record: dict[str, Any]) -> list[dict[str, Any]]:
    """One summary event plus one per-variant event (baseline, candidate) for filtering."""
    proposal = record.get("proposal") if isinstance(record.get("proposal"), dict) else {}
    patch = proposal.get("patch") if isinstance(proposal.get("patch"), dict) else {}
    agg = record.get("aggregate") if isinstance(record.get("aggregate"), dict) else {}
    held = record.get("heldOutTest") if isinstance(record.get("heldOutTest"), dict) else {}
    base = record.get("baseline") if isinstance(record.get("baseline"), dict) else {}
    cand = record.get("candidate") if isinstance(record.get("candidate"), dict) else {}
    eval_id = _s(record.get("_id"))
    user = "march-optimizer:" + employee_hash(record.get("triggeredFor"))
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    patch_value = patch.get("value")
    common = _clean({
        "evaluationId": eval_id,
        "suiteVersion": _s(record.get("suiteVersion")),
        "gateDecision": _s(record.get("gateDecision")),
        "employeeHash": employee_hash(record.get("triggeredFor")),
        "baselineVersionId": _s(record.get("baselineVersionId")),
        "candidateVersionId": _s(record.get("candidateVersionId")),
        "patchPath": _s(patch.get("path")),
        "patchValue": patch_value if isinstance(patch_value, (bool, int, float)) else None,
        "repetitions": _num(record.get("repetitions")),
    })
    summary = _clean({
        **common,
        "failureCodes": _codes(record.get("failureCodes")),
        "baselineMean": _num(agg.get("baselineMean")),
        "candidateMean": _num(agg.get("candidateMean")),
        "gain": _num(agg.get("gain")),
        "noiseBand": _num(agg.get("noiseBand", base.get("noiseBand"))),
        "fixedCases": [_s(c) for c in agg.get("fixedCases") or []][:50],
        "regressedCases": [_s(c) for c in agg.get("regressedCases") or []][:50],
        "heldOutBaseline": _split(held.get("baseline")),
        "heldOutCandidate": _split(held.get("candidate")),
        "heldOutBaselineCriticalCount": len(held.get("baselineCritical") or []),
        "heldOutCandidateCriticalCount": len(held.get("candidateCritical") or []),
    })
    events = [{"event_id": eval_id, "user_id": user, "event": "march_evaluation",
               "timestamp": ts, "properties": summary}]
    for variant, part, version_id, test in (
        ("baseline", base, record.get("baselineVersionId"), held.get("baseline")),
        ("candidate", cand, record.get("candidateVersionId"), held.get("candidate")),
    ):
        if not part or version_id is None:
            continue
        rates = _rates(part.get("rates"))
        events.append({
            "event_id": f"{eval_id}:{variant}" if eval_id else None,
            "user_id": user,
            "event": "march_evaluation_variant",
            "timestamp": ts,
            "properties": _clean({
                **common,
                "variant": variant,
                "harnessVersionId": _s(version_id),
                "rates": rates,
                "meanRate": sum(rates) / len(rates) if rates else None,
                "heldOutTest": _split(test),
            }),
        })
    return events


def _post(key: str, events: list[dict[str, Any]]) -> None:
    try:
        import httpx

        url = (API_URL if API_URL.endswith("/") else API_URL + "/") + "events/track"
        resp = httpx.post(url, json=[{k: v for k, v in e.items() if v is not None} for e in events],
                          headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_S)
        if resp.status_code >= 300:
            log.warning("raindrop ingest returned HTTP %s", resp.status_code)
    except Exception as exc:  # Telemetry must never break a run.
        log.warning("raindrop send failed: %s", type(exc).__name__)


def _send(events: list[dict[str, Any]]) -> None:
    key = _key()
    if not key or not events:
        return
    try:
        threading.Thread(target=_post, args=(key, events), name="raindrop", daemon=True).start()
    except Exception as exc:
        log.warning("raindrop thread failed: %s", type(exc).__name__)


def trace_run(run: dict[str, Any], variant: str | None = None) -> None:
    if not _key():
        return
    try:
        _send([redact_run(run, variant)])
    except Exception as exc:
        log.warning("raindrop trace_run failed: %s", type(exc).__name__)


def trace_evaluation(record: dict[str, Any]) -> None:
    if not _key():
        return
    try:
        _send(redact_evaluation(record))
    except Exception as exc:
        log.warning("raindrop trace_evaluation failed: %s", type(exc).__name__)
