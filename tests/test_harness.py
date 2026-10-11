import pytest

from march.harness import BASELINE, Harness, PatchRejected, apply_patch, validate_proposal

ORG = "demo_office"


def proposal(path, value, **extra):
    return {"patch": {"op": "replace", "path": path, "value": value}, "hypothesis": "h", **extra}


@pytest.mark.parametrize("path", ["/security/scope", "/retrieval/../workflow", "/approvals/required",
                                  "/evaluator/threshold", "/retrieval/semanticTopk"])
def test_patch_outside_allowlist_rejected(path):
    with pytest.raises(PatchRejected):
        validate_proposal(proposal(path, True))


@pytest.mark.parametrize("path,value", [("/retrieval/semanticTopK", 11), ("/retrieval/semanticTopK", 2),
                                        ("/retrieval/maxContextTokens", 9000), ("/response/maxSpokenSentences", 0),
                                        ("/retrieval/pinExplicitPreferences", 1), ("/retrieval/semanticTopK", True)])
def test_patch_outside_bounds_or_type_rejected(path, value):
    with pytest.raises(PatchRejected):
        validate_proposal(proposal(path, value))


def test_extra_fields_and_other_ops_rejected():
    with pytest.raises(PatchRejected):
        validate_proposal(proposal("/retrieval/semanticTopK", 8, code="import os"))
    bad = proposal("/retrieval/semanticTopK", 8)
    bad["patch"]["op"] = "add"
    with pytest.raises(PatchRejected):
        validate_proposal(bad)


def test_no_op_patch_rejected():
    with pytest.raises(PatchRejected):
        apply_patch(BASELINE, {"op": "replace", "path": "/retrieval/semanticTopK", "value": 6})


def test_promotion_is_compare_and_set(db):
    h = Harness(db, "demo", ORG)
    base = h.active("emp_asha")
    c1 = h.create_candidate("emp_asha", proposal("/retrieval/pinExplicitPreferences", True), [])
    c2 = h.create_candidate("emp_asha", proposal("/retrieval/semanticTopK", 8), [])
    assert c1["parentVersionId"] == c2["parentVersionId"] == base["_id"]
    assert h.promote("emp_asha", c1["_id"], "eval1") is True
    assert h.promote("emp_asha", c2["_id"], "eval2") is False  # Stale parent cannot overwrite.
    assert h.active("emp_asha")["_id"] == c1["_id"]
    assert h.active("emp_ben")["_id"] != c1["_id"]  # Other employees keep their own version.


def test_promoted_payload_immutable_and_rollback(db):
    h = Harness(db, "demo", ORG)
    base = h.active("emp_casey")
    c = h.create_candidate("emp_casey", proposal("/retrieval/pinExplicitPreferences", True), [])
    h.promote("emp_casey", c["_id"], "e")
    assert db.harness_versions.find_one({"_id": base["_id"]})["config"] == BASELINE
    assert h.rollback("emp_casey", base["_id"], "demo rollback")
    assert h.active("emp_casey")["_id"] == base["_id"]


def test_in_flight_run_keeps_pinned_version(orch, store, db, asha):
    h = Harness(db, "demo", ORG)
    pinned = h.active("emp_asha")
    c = h.create_candidate("emp_asha", proposal("/retrieval/pinExplicitPreferences", True), [])
    h.promote("emp_asha", c["_id"], "e")
    run = orch.handle(asha, "find a 30 minute slot with Ben tomorrow", "november_text", version=pinned)
    assert run["harnessVersionId"] == pinned["_id"]
    fresh = orch.handle(asha, "find a 30 minute slot with Ben tomorrow", "november_text")
    assert fresh["harnessVersionId"] == c["_id"]


def test_candidate_with_critical_failure_rejected_regardless_of_score(db, store, orch, monkeypatch):
    from march import improve

    def fake_suite(store_, orch_, org, version, splits):
        cand = version["patch"] is not None
        results = [
            {"id": "x1", "split": "dev", "critical": False, "pass": cand, "failures": [] if cand else ["ignored_preference:afternoon"], "runId": "r1"},
            {"id": "x2", "split": "val", "critical": True, "pass": not cand, "failures": ["negation_lost"] if cand else [], "runId": "r2"},
        ]
        by = {}
        for r in results:
            if r["split"] in splits:
                b = by.setdefault(r["split"], {"passed": 0, "total": 0})
                b["total"] += 1
                b["passed"] += int(r["pass"])
        return {"versionId": version["_id"], "results": [r for r in results if r["split"] in splits],
                "bySplit": by, "invalidRecallCases": [],
                "criticalFailures": [r["id"] for r in results if r["critical"] and not r["pass"] and r["split"] in splits]}

    monkeypatch.setattr(improve, "run_suite", fake_suite)
    monkeypatch.setattr(improve, "seed_memories", lambda *a, **k: 0)
    monkeypatch.setattr(improve, "wait_for_index", lambda *a, **k: True)
    monkeypatch.setattr(improve, "propose", lambda *a: (proposal("/retrieval/pinExplicitPreferences", True), "{}"))
    record = improve.run_cycle(store, store, orch, ORG, "emp_asha", progress=lambda m: None)
    assert record["gateDecision"] == "rejected"
    assert "critical_failure" in record["failureCodes"]
    assert Harness(db, "demo", ORG).active("emp_asha")["patch"] is None  # Baseline still active.
