import json
import threading
from datetime import UTC, datetime, timedelta

import pytest

from march import telemetry

SECRETS = [
    "Please email Priya that I prefer afternoons",  # transcript
    "Hi Priya, confidential budget numbers attached",  # email body
    "Q3 budget review",  # subject
    "priya@example.com",  # recipient
    "Asha prefers afternoon meetings after 2pm",  # memory text
    "https://news.example.com/private-article",  # browsing URL
    "Article body scraped from the web page",  # web content
    "mongodb+srv://user:pass@cluster0.example.net",  # mongo URI
    "ya29.SECRET_OAUTH_TOKEN",  # token
    "emp_asha",  # raw employee id
    "0.8731",  # voice score
]


def realistic_run():
    start = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)
    return {
        "_id": "run_123",
        "mode": "demo",
        "orgId": "demo_office",
        "employeeId": "emp_asha",
        "inputSource": "november_voice",
        "identitySource": "voice_match",
        "voice": {"status": "matched", "employeeId": "emp_asha", "best": 0.8731, "margin": 0.21,
                  "scores": {"emp_asha": 0.8731, "emp_ben": 0.4}, "embedding": [0.1, 0.2]},
        "transcript": SECRETS[0],
        "state": "completed",
        "capability": "prepare_mail",
        "november": {"normalizedCommand": SECRETS[0], "intent": {"goal": SECRETS[0]}},
        "result": {"status": "prepared", "to": SECRETS[3], "subject": SECRETS[2], "body": SECRETS[1],
                   "relatedNotes": [{"id": "m1", "text": SECRETS[4]}],
                   "sources": [{"url": SECRETS[5], "content": SECRETS[6]}]},
        "pendingActionIds": ["act_1"],
        "preferencesUsed": ["scheduling.afternoons"],
        "selectedMemoryIds": ["m1", "m2"],
        "recallMethod": "vector_autoembed",
        "harnessVersionId": "hv_base",
        "harnessLabel": "baseline",
        "failureCodes": [f"ValueError:{SECRETS[7]} {SECRETS[8]}"],
        "startedAt": start,
        "completedAt": start + timedelta(milliseconds=1500),
    }


def realistic_eval():
    return {
        "_id": "ev_1", "mode": "eval", "orgId": "demo_office", "triggeredFor": "emp_asha",
        "suiteVersion": "suite_v2", "baselineVersionId": "hv_base", "candidateVersionId": "hv_cand",
        "repetitions": 3, "gateDecision": "rejected",
        "failureCodes": ["gain_0.000_not_above_noise_0.000", f"PatchRejected:{SECRETS[4]}"],
        "proposal": {"patch": {"op": "replace", "path": "/retrieval/pinExplicitPreferences", "value": True},
                     "hypothesis": SECRETS[4], "expectedEffect": SECRETS[0], "regressionRisk": "low"},
        "baseline": {"rates": [0.5, 0.5, 0.5], "noiseBand": 0.0,
                     "first": {"results": [{"id": "c1", "runId": "r", "failures": [SECRETS[1]]}]}},
        "candidate": {"rates": [0.75, 0.75, 0.75], "first": {"results": [{"failures": [SECRETS[5]]}]}},
        "aggregate": {"baselineMean": 0.5, "candidateMean": 0.75, "gain": 0.25, "noiseBand": 0.0,
                      "fixedCases": ["dev_sched_1"], "regressedCases": []},
        "heldOutTest": {"baseline": {"passed": 2, "total": 4}, "candidate": {"passed": 3, "total": 4},
                        "baselineCritical": [], "candidateCritical": []},
    }


def _assert_clean(payload):
    blob = json.dumps(payload, default=str)
    for secret in SECRETS:
        assert secret not in blob, secret
    for forbidden in ("transcript", "body", "subject", "\"to\"", "text", "url", "embedding",
                      "scores", "\"november\"", "orgId", "hypothesis", "mongodb"):
        assert forbidden not in blob, forbidden


def test_run_payload_is_redacted():
    event = telemetry.redact_run(realistic_run())
    _assert_clean(event)
    p = event["properties"]
    assert p["employeeHash"] == telemetry.employee_hash("emp_asha") and len(p["employeeHash"]) == 12
    assert event["user_id"] == p["employeeHash"]
    assert p["voiceStatus"] == "matched"
    assert p["preferencesUsedCount"] == 1 and p["selectedMemoryCount"] == 2
    assert p["harnessVersionId"] == "hv_base" and p["variant"] == "live"
    assert p["failureCodes"] == ["ValueError"]
    assert p["latencyMs"] == 1500


def test_evaluation_payload_is_redacted_and_has_variants():
    events = telemetry.redact_evaluation(realistic_eval())
    _assert_clean(events)
    summary, *variants = events
    assert summary["properties"]["gain"] == 0.25
    assert summary["properties"]["patchPath"] == "/retrieval/pinExplicitPreferences"
    assert summary["properties"]["failureCodes"] == ["gain_0.000_not_above_noise_0.000", "PatchRejected"]
    assert {(v["properties"]["variant"], v["properties"]["harnessVersionId"]) for v in variants} == {
        ("baseline", "hv_base"), ("candidate", "hv_cand")}


def test_no_network_without_key(monkeypatch):
    monkeypatch.delenv("RAINDROP_WRITE_KEY", raising=False)
    calls = []
    monkeypatch.setattr(telemetry, "_post", lambda *a: calls.append(a))
    monkeypatch.setattr(threading, "Thread", lambda *a, **k: calls.append(k))
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(a))
    telemetry.trace_run(realistic_run())
    telemetry.trace_evaluation(realistic_eval())
    assert calls == []


def test_sends_redacted_payload_with_key(monkeypatch):
    monkeypatch.setenv("RAINDROP_WRITE_KEY", "rk_test")
    sent = []
    import httpx

    class Resp:
        status_code = 204

    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: sent.append((url, json, headers)) or Resp())
    telemetry._post("rk_test", [telemetry.redact_run(realistic_run())])
    url, body, headers = sent[0]
    assert url.endswith("/v1/events/track") and headers["Authorization"] == "Bearer rk_test"
    _assert_clean(body)


def test_send_errors_never_propagate(monkeypatch):
    monkeypatch.setenv("RAINDROP_WRITE_KEY", "rk_test")
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    telemetry._post("rk_test", [{"event": "x"}])  # Network failure swallowed.

    def bad_redact(*a, **k):
        raise RuntimeError("bad record")

    monkeypatch.setattr(telemetry, "redact_run", bad_redact)
    monkeypatch.setattr(telemetry, "redact_evaluation", bad_redact)
    telemetry.trace_run({})
    telemetry.trace_evaluation({})

    def bad_thread(*a, **k):
        raise RuntimeError("no threads")

    monkeypatch.setattr(threading, "Thread", bad_thread)
    telemetry._send([{"event": "x"}])


@pytest.mark.parametrize("run", [{}, {"voice": None, "result": None, "preferencesUsed": None}])
def test_sparse_runs_do_not_crash(run):
    assert telemetry.redact_run(run)["properties"]["employeeHash"]
