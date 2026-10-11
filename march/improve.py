"""One bounded improvement cycle (doc 07). The optimizer may only propose one allowlisted patch;
gates, evaluator and expected outcomes are fixed code and data outside its reach."""

import json
import os
import statistics
import urllib.request
from collections import Counter
from collections.abc import Callable
from typing import Any

from march import telemetry
from march.db import Store, new_id, now
from march.evaluation import EVAL_CLOCK, run_suite, seed_memories, wait_for_index
from march.harness import ALLOWLIST, Harness, PatchRejected, validate_proposal
from march.orchestrator import Orchestrator

OPTIMIZER_MODEL = os.getenv("MARCH_OPTIMIZER_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
REPEATS = int(os.getenv("MARCH_EVAL_REPEATS", "3"))
SUITE_VERSION = os.getenv("MARCH_SUITE", "suite_v2")

FIELD_HELP = {
    "/retrieval/semanticTopK": "how many memories semantic vector search returns per request",
    "/retrieval/recentTurnPairs": "recent conversation turns kept in context (not wired in this build; changing it has no effect)",
    "/retrieval/pinExplicitPreferences": "always load the employee's explicit typed preferences by direct indexed read, instead of only when semantic search happens to return them",
    "/retrieval/includeLinkedNotes": "expand linked notes (not wired in this build; changing it has no effect)",
    "/retrieval/maxContextTokens": "context budget (not wired in this build; changing it has no effect)",
    "/workflow/schedulingPreferencePass": "for scheduling requests only, load scheduling.* preferences by direct read",
    "/workflow/answerCoveragePass": "extra coverage check on answers (not wired in this build; changing it has no effect)",
    "/workflow/maxReadToolCalls": "cap on read tool calls (not wired in this build; changing it has no effect)",
    "/response/maxSpokenSentences": "spoken response length (not wired in this build; changing it has no effect)",
}

PROPOSAL_SCHEMA = {
    "type": "object",
    "required": ["patch", "hypothesis", "expectedEffect", "regressionRisk"],
    "properties": {
        "patch": {
            "type": "object",
            "required": ["op", "path", "value"],
            "properties": {
                "op": {"type": "string", "enum": ["replace"]},
                "path": {"type": "string", "enum": sorted(ALLOWLIST)},
                "value": {"type": ["boolean", "integer"]},
            },
        },
        "hypothesis": {"type": "string"},
        "expectedEffect": {"type": "string"},
        "regressionRisk": {"type": "string"},
    },
}


def propose(config: dict[str, Any], failure_summary: dict[str, int], tried: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    """Ask the local model for ONE patch. Returns (proposal, raw_text)."""
    allowed = {p: {"type": t.__name__, "min": lo, "max": hi, "meaning": FIELD_HELP[p]}
               for p, (t, lo, hi) in ALLOWLIST.items()}
    prompt = (
        "You tune a personal assistant's context-retrieval harness. Propose exactly ONE patch "
        "to ONE allowlisted config path that is most likely to fix the observed structural "
        "failures without weakening anything else. You cannot change safety, scope, approvals, "
        "evaluators or test expectations.\n\n"
        f"Current config:\n{json.dumps(config, indent=2)}\n\n"
        f"Allowlisted paths:\n{json.dumps(allowed, indent=2)}\n\n"
        f"Failure codes on development cases (code: count):\n{json.dumps(failure_summary, indent=2)}\n\n"
        f"Previously tried patches and outcomes:\n{json.dumps(tried, indent=2)}\n\n"
        "Return JSON only: {\"patch\": {\"op\": \"replace\", \"path\": ..., \"value\": ...}, "
        "\"hypothesis\": ..., \"expectedEffect\": ..., \"regressionRisk\": ...}"
    )
    body = json.dumps({
        "model": OPTIMIZER_MODEL, "stream": False, "format": PROPOSAL_SCHEMA,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0, "seed": 7, "num_predict": 400},
    }).encode()
    request = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=180) as response:
        raw = json.loads(response.read())["message"]["content"]
    return json.loads(raw), raw


def _rate(evaluation: dict[str, Any], splits: tuple[str, ...]) -> float:
    passed = sum(evaluation["bySplit"].get(s, {}).get("passed", 0) for s in splits)
    total = sum(evaluation["bySplit"].get(s, {}).get("total", 0) for s in splits)
    return passed / total if total else 0.0


def run_cycle(
    demo_store: Store,
    eval_store: Store,
    eval_orch: Orchestrator,
    org_id: str,
    employee_id: str,
    progress: Callable[[str], None] = print,
) -> dict[str, Any]:
    harness = Harness(demo_store.db, "demo", org_id)
    parent = harness.active(employee_id)
    evaluation_id = new_id()
    record: dict[str, Any] = {"_id": evaluation_id, "mode": "eval", "orgId": org_id,
                              "triggeredFor": employee_id, "suiteVersion": SUITE_VERSION,
                              "baselineVersionId": parent["_id"], "startedAt": now(),
                              "repetitions": REPEATS, "clock": EVAL_CLOCK.isoformat()}
    progress("Seeding eval fixture memories in march_eval…")
    seed_memories(eval_store, org_id, SUITE_VERSION)
    if not wait_for_index(eval_store, org_id, suite=SUITE_VERSION):
        record.update(gateDecision="aborted", failureCodes=["vector_index_not_synced"])
        eval_store.db.evaluations.insert_one(record)
        telemetry.trace_evaluation(record)
        return record
    dv = ("dev", "val")
    from march.evaluation import AtlasRecallCache

    eval_orch.recall_cache = AtlasRecallCache(eval_store, SUITE_VERSION)  # Embed each query once.
    progress("Evaluating active version (baseline) on dev+val…")
    base_runs = [run_suite(eval_store, eval_orch, org_id, parent, dv) for _ in range(REPEATS)]
    base_rates = [_rate(e, dv) for e in base_runs]
    noise = max(base_rates) - min(base_rates)
    failing = Counter(f for r in base_runs[0]["results"] if r["split"] == "dev" for f in r["failures"])
    # Structural evidence: an explicit preference existed but the failing run did not use it.
    from march.evaluation import fixture_memories

    keys = {emp: {k for kind, k, _, _ in items if kind == "preference"}
            for emp, items in fixture_memories(SUITE_VERSION).items()}
    for r in base_runs[0]["results"]:
        if r["split"] == "dev" and not r["pass"] and r.get("employee"):
            for key in sorted(keys[r["employee"]] - set(r.get("preferencesUsed") or [])):
                failing[f"explicit_preference_existed_but_unused:{key}"] += 1
    record.update(baseline={"rates": base_rates, "noiseBand": noise, "first": base_runs[0]})
    progress(f"Baseline dev+val pass rates {base_rates}; failure codes {dict(failing)}")
    if not failing:
        record.update(gateDecision="no_failures_to_fix", completedAt=now())
        eval_store.db.evaluations.insert_one(record)
        telemetry.trace_evaluation(record)
        return record
    tried = [
        {"patch": v.get("patch"), "status": v.get("lifecycleStatus"), "reasons": v.get("rejectionReasons")}
        for v in demo_store.db.harness_versions.find(
            {"mode": "demo", "orgId": org_id, "employeeId": employee_id, "patch": {"$ne": None}})
    ]
    progress(f"Asking local optimizer ({OPTIMIZER_MODEL}) for one allowlisted patch…")
    try:
        proposal, raw = propose(parent["config"], dict(failing), tried)
        validate_proposal(proposal)
        candidate = harness.create_candidate(
            employee_id, proposal, [r["runId"] for r in base_runs[0]["results"] if not r["pass"]][:10]
        )
    except (PatchRejected, ValueError, KeyError, OSError) as exc:
        record.update(gateDecision="proposal_rejected", failureCodes=[f"{type(exc).__name__}:{exc}"],
                      completedAt=now())
        eval_store.db.evaluations.insert_one(record)
        telemetry.trace_evaluation(record)
        return record
    record.update(candidateVersionId=candidate["_id"], proposal=proposal)
    progress(f"Candidate patch {proposal['patch']}; evaluating on dev+val…")
    cand_runs = [run_suite(eval_store, eval_orch, org_id, candidate, dv) for _ in range(REPEATS)]
    cand_rates = [_rate(e, dv) for e in cand_runs]
    reasons: list[str] = []
    if any(e["invalidRecallCases"] for e in base_runs + cand_runs):
        reasons.append("evaluation_invalid_recall_fallback")
    if any(e["criticalFailures"] for e in cand_runs):
        reasons.append("critical_failure")
    base_mean, cand_mean = statistics.mean(base_rates), statistics.mean(cand_rates)
    gain = cand_mean - base_mean
    if gain <= noise:
        reasons.append(f"gain_{gain:.3f}_not_above_noise_{noise:.3f}")
    for split in dv:
        b = statistics.mean(_rate(e, (split,)) for e in base_runs)
        c = statistics.mean(_rate(e, (split,)) for e in cand_runs)
        if c < b:
            reasons.append(f"{split}_regressed")
    base_pass = {r["id"] for r in base_runs[0]["results"] if r["pass"]}
    cand_pass = {r["id"] for r in cand_runs[0]["results"] if r["pass"]}
    if not (cand_pass - base_pass):
        reasons.append("no_previously_failing_case_fixed")
    regressed = sorted(base_pass - cand_pass)
    if regressed:
        reasons.append(f"per_case_regressions:{','.join(regressed)}")
    progress("Held-out test split (reported only, never shown to optimizer)…")
    base_test = run_suite(eval_store, eval_orch, org_id, parent, ("test",))
    cand_test = run_suite(eval_store, eval_orch, org_id, candidate, ("test",))
    record.update(
        candidate={"rates": cand_rates, "first": cand_runs[0]},
        aggregate={"baselineMean": base_mean, "candidateMean": cand_mean, "gain": gain,
                   "noiseBand": noise, "fixedCases": sorted(cand_pass - base_pass),
                   "regressedCases": regressed},
        heldOutTest={"baseline": base_test["bySplit"].get("test"), "candidate": cand_test["bySplit"].get("test"),
                     "baselineCritical": base_test["criticalFailures"], "candidateCritical": cand_test["criticalFailures"]},
        tokenUsage="unavailable (local Ollama; not counted)",
    )
    if reasons:
        harness.reject(candidate["_id"], evaluation_id, reasons)
        record.update(gateDecision="rejected", failureCodes=reasons)
    else:
        promoted = harness.promote(employee_id, candidate["_id"], evaluation_id)
        record.update(gateDecision="promoted" if promoted else "stale_parent_reevaluate")
    record["completedAt"] = now()
    eval_store.db.evaluations.insert_one(record)
    telemetry.trace_evaluation(record)
    progress(f"Decision: {record['gateDecision']} {reasons}")
    return record
