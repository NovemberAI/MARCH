# 07. Bounded recursive harness improvement

## What is allowed to improve

The frozen NovemberAI ASR, intent schema and deterministic safety policy remain the foundation. MARCH adapts how personal context is retrieved and how non-security workflow checks are arranged. It does not fine-tune models or let an agent edit its own source code.

A user preference becoming a memory is useful, but not sufficient evidence of harness improvement. Demonstrate that a changed reusable retrieval/workflow policy improves previously failing tasks.

## Initial schema

Use one versioned `HarnessConfig` per employee, derived from an identical base. Existing NovemberAI settings are wrapped rather than duplicated.

```json
{
  "schemaVersion": 1,
  "retrieval": {
    "semanticTopK": 6,
    "recentTurnPairs": 4,
    "pinExplicitPreferences": false,
    "includeLinkedNotes": false,
    "maxContextTokens": 4000
  },
  "workflow": {
    "schedulingPreferencePass": false,
    "answerCoveragePass": false,
    "maxReadToolCalls": 4
  },
  "response": {
    "maxSpokenSentences": 2
  }
}
```

This intentionally simple baseline may miss optional convenience preferences. It must never disable account scoping, current explicit task constraints, consent, source validation, required approvals or other safety rules. Use the same baseline consistently and disclose it. Do not deliberately break a working NovemberAI safety behavior to manufacture an improvement.

Allowed ranges: semanticTopK 3-10; recentTurnPairs 2-6; maxContextTokens 1500-6000; maxReadToolCalls 2-6; maxSpokenSentences 1-3. Boolean fields can toggle. Hard global budgets cannot be raised by a candidate.

## Proposal contract

A fixed optimizer receives the current config, minimized scoped failure evidence, tried/rejected edits and measured outcomes. It returns one patch on one allowlisted path:

```json
{
  "parentVersionId": "example-parent",
  "patch": {"op": "replace", "path": "/retrieval/pinExplicitPreferences", "value": true},
  "hypothesis": "Scheduling missed an existing preference because semantic retrieval did not include it.",
  "evidenceRunIds": ["example-run"],
  "expectedEffect": "Include active explicit preferences before historical notes.",
  "regressionRisk": "More input context and possible irrelevant preference inclusion."
}
```

Validate with a strict schema and allowlist. Reject extra fields, arbitrary code, arbitrary prompt replacements, evaluator edits, credential changes or source-file paths. A rationale may mention an observed fixture; the shipped policy must not contain fixture names, answer literals or task IDs. In this MVP, a structured patch makes that distinction easy to enforce.

Do not let an LLM-returned parent ID select another employee's version. Load parent through the current server scope.

## Improvement cycle

1. Finish a task and collect explicit correction or verified structural failure.
2. Store the evidence and current version in MongoDB.
3. Propose one small edit. Start with one candidate; a second is optional within budget.
4. Validate patch and materialize an immutable candidate version.
5. Run baseline and candidate against the same frozen fixture snapshot, model configuration and paired seeds, using only fixture adapters.
6. Compute task success, constraint satisfaction, leakage, approval failures, latency and token usage where available.
7. Apply hard gates before quality/cost comparisons.
8. Promote with compare-and-set only if gates pass; otherwise retain the old version and store the reason.
9. Pin the promoted version for new runs. Existing runs continue on their original version.
10. New runs can produce evidence for another iteration. No unbounded autonomous loop.

Raindrop can capture trajectories, signals and comparisons. MongoDB stores the canonical candidate, fixture/suite version, result and promotion decision. A vendor issue detector is an input, not the final authority on privacy or correctness.

## Acceptance gates

### Mandatory

- Zero failures in cross-employee scope tests.
- Zero unauthorized external-action attempts or approval bypasses.
- Zero live connector calls from evaluation.
- Current explicit task constraints and negations remain intact.
- Patch changes only an allowlisted config field within bounds.
- No fixture answers/identities embedded in shipped policy.
- No regression in deterministic critical task checks.

Any failure rejects the candidate regardless of score.

### Quality and cost

Use 12 development cases, 6 validation cases and 6 untouched final-test cases as the target small suite. Development and validation influence selection; the final test does not feed the optimizer.

Measure baseline variation with three repeated runs when budget allows. Define the initial noise band as max minus min baseline pass rate on the development+validation set. This is a deliberately simple demo heuristic inspired by RRSI, not a statistically calibrated estimator or reproduction of its full method.

Accept only if the candidate's mean pass-rate gain exceeds that observed band, neither development nor validation mean decreases, and no critical per-case check regresses. Require an absolute improvement of at least one distinct previously failing task. Retain raw counts and denominators.

Initial optional efficiency gates: average reported input+output tokens no more than 25% above baseline and p95 latency no more than 25% above baseline, unless a human explicitly approves the tradeoff. Those are proposed product budgets, not paper hyperparameters. With tiny sample counts, report latency variability honestly. If token usage is unavailable, record unavailable and use a hard call-count/timeout cap instead; do not invent zero-cost measurements.

If repeats are cut due to time, label the result preliminary, disable unattended promotion, and require a review of the small-run evidence. Do not claim statistically significant improvement.

## Evaluation isolation

The evaluator process starts with `mode=eval`, uses `march_eval`, has no live connector credentials and only fixture tool adapters. Allow outbound requests only to the selected authorized model/embedding providers, Atlas and approved redacted telemetry endpoints. Block Google/Aside execution adapters regardless of model output.

A failed attempt to call a live tool is itself an evaluation failure. Replaying an email task must not replay an actual email send.

## Concrete demo

Asha's afternoon preference is already stored before the baseline run. On a scheduling request, v1 retrieves related notes but misses that preference and proposes a morning. The employee correction is recorded. Optimizer proposes pinExplicitPreferences=true. The system tests the candidate on varied calendar and email requests for all three fictional employees, including negative cases. A winning version must retrieve the preference by policy, not by hardcoded response. Ben and Casey retain their own rules.

Do not force the baseline to fail at presentation time or preprogram the desired patch. If the candidate fails tests, show the rejection and explain it. A clearly labeled pre-recorded run may supplement a live demo, but must reference its real run/version IDs.

## Versioning and rollback

Store parent, config hash, patch, evidence, evaluation and lifecycle status. The active pointer lives on the employee record. Promotion checks the expected parent is still active; stale candidates require reevaluation. Rollback selects a known prior immutable version and logs the reason. Private facts are not copied from one employee's harness to another.

## Three-hour scope

Implement one full measured cycle. Add a second only after core routing, memory, approvals and tests work. Skip population search, model training, annealing schedules, graph evolution, arbitrary code mutation and multi-agent debate. The new feature is the controlled feedback loop, not the number of agents.
