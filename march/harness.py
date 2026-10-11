"""Versioned, bounded harness configuration (doc 07). Security is not representable here:
identity, scope, approvals, credentials, evaluators and expected outcomes are not fields."""

import copy
import hashlib
import json
from typing import Any

from march.db import SCHEMA_VERSION, new_id, now

BASELINE: dict[str, Any] = {
    "schemaVersion": 1,
    "retrieval": {
        "semanticTopK": 6,
        "recentTurnPairs": 4,
        "pinExplicitPreferences": False,
        "includeLinkedNotes": False,
        "maxContextTokens": 4000,
    },
    "workflow": {
        "schedulingPreferencePass": False,
        "answerCoveragePass": False,
        "maxReadToolCalls": 4,
    },
    "response": {"maxSpokenSentences": 2},
}

# Path -> (type, min, max). Anything else is rejected.
ALLOWLIST: dict[str, tuple[type, int | None, int | None]] = {
    "/retrieval/semanticTopK": (int, 3, 10),
    "/retrieval/recentTurnPairs": (int, 2, 6),
    "/retrieval/pinExplicitPreferences": (bool, None, None),
    "/retrieval/includeLinkedNotes": (bool, None, None),
    "/retrieval/maxContextTokens": (int, 1500, 6000),
    "/workflow/schedulingPreferencePass": (bool, None, None),
    "/workflow/answerCoveragePass": (bool, None, None),
    "/workflow/maxReadToolCalls": (int, 2, 6),
    "/response/maxSpokenSentences": (int, 1, 3),
}
PROPOSAL_FIELDS = {"patch", "hypothesis", "evidenceRunIds", "expectedEffect", "regressionRisk"}

# Fixed tool constants. Not optimizer-controlled.
TOOL_CONSTANTS: dict[str, Any] = {
    "workdayStartHour": 9,
    "workdayEndHour": 17,
    "defaultMeetingMinutes": 30,
    "slotStepMinutes": 15,
    "maxSlots": 3,
    "emailGreeting": "Hi",
    "emailSignoff": "Thanks",
    "emailMaxSentences": 3,
}


class PatchRejected(ValueError):
    pass


def config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def validate_proposal(proposal: Any) -> dict[str, Any]:
    if not isinstance(proposal, dict) or set(proposal) - PROPOSAL_FIELDS or "patch" not in proposal:
        raise PatchRejected("proposal_shape")
    patch = proposal["patch"]
    if not isinstance(patch, dict) or set(patch) != {"op", "path", "value"}:
        raise PatchRejected("patch_shape")
    if patch["op"] != "replace":
        raise PatchRejected("op_not_allowed")
    rule = ALLOWLIST.get(patch["path"])
    if rule is None:
        raise PatchRejected("path_not_allowlisted")
    kind, lo, hi = rule
    value = patch["value"]
    if kind is bool and not isinstance(value, bool):
        raise PatchRejected("type")
    if kind is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise PatchRejected("type")
    if kind is int and not (lo <= value <= hi):  # type: ignore[operator]
        raise PatchRejected("out_of_bounds")
    for text_field in ("hypothesis", "expectedEffect", "regressionRisk"):
        if text_field in proposal and len(str(proposal[text_field])) > 600:
            raise PatchRejected("rationale_too_long")
    return proposal


def apply_patch(config: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(config)
    _, section, key = patch["path"].split("/")
    if out[section][key] == patch["value"]:
        raise PatchRejected("no_op")
    out[section][key] = patch["value"]
    return out


class Harness:
    def __init__(self, db: Any, mode: str, org_id: str) -> None:
        self.db, self.mode, self.org_id = db, mode, org_id

    def _key(self, employee_id: str) -> dict[str, str]:
        return {"mode": self.mode, "orgId": self.org_id, "employeeId": employee_id}

    def ensure_baseline(self, employee_id: str) -> dict[str, Any]:
        key = self._key(employee_id)
        version_id = f"{self.mode}:{employee_id}:v1"
        self.db.harness_versions.update_one(
            {"_id": version_id},
            {
                "$setOnInsert": {
                    **key,
                    "schemaVersion": SCHEMA_VERSION,
                    "label": "v1-baseline",
                    "parentVersionId": None,
                    "config": BASELINE,
                    "configHash": config_hash(BASELINE),
                    "patch": None,
                    "rationale": "Identical documented baseline for every employee (doc 07).",
                    "lifecycleStatus": "active",
                    "createdBy": "system",
                    "createdAt": now(),
                }
            },
            upsert=True,
        )
        self.db.employees.update_one(
            {**key, "activeHarnessVersionId": None}, {"$set": {"activeHarnessVersionId": version_id}}
        )
        return self.db.harness_versions.find_one({"_id": version_id})

    def active(self, employee_id: str) -> dict[str, Any]:
        employee = self.db.employees.find_one(self._key(employee_id)) or {}
        version_id = employee.get("activeHarnessVersionId")
        doc = self.db.harness_versions.find_one({"_id": version_id, **self._key(employee_id)}) if version_id else None
        return doc or self.ensure_baseline(employee_id)

    def create_candidate(self, employee_id: str, proposal: dict[str, Any], evidence: list[str]) -> dict[str, Any]:
        validate_proposal(proposal)
        parent = self.active(employee_id)  # Parent always loaded through server scope.
        config = apply_patch(parent["config"], proposal["patch"])
        count = self.db.harness_versions.count_documents(self._key(employee_id))
        doc = {
            "_id": new_id(),
            **self._key(employee_id),
            "schemaVersion": SCHEMA_VERSION,
            "label": f"v{count + 1}-candidate",
            "parentVersionId": parent["_id"],
            "config": config,
            "configHash": config_hash(config),
            "patch": proposal["patch"],
            "rationale": {k: proposal.get(k) for k in ("hypothesis", "expectedEffect", "regressionRisk")},
            "evidenceRunIds": evidence,
            "lifecycleStatus": "candidate",
            "createdBy": "optimizer",
            "createdAt": now(),
        }
        self.db.harness_versions.insert_one(doc)
        return doc

    def promote(self, employee_id: str, candidate_id: str, evaluation_id: str) -> bool:
        candidate = self.db.harness_versions.find_one({"_id": candidate_id, **self._key(employee_id)})
        if not candidate:
            return False
        swapped = self.db.employees.update_one(
            {**self._key(employee_id), "activeHarnessVersionId": candidate["parentVersionId"]},
            {"$set": {"activeHarnessVersionId": candidate_id}},
        )
        if swapped.modified_count != 1:
            return False  # Stale parent: someone else promoted first; must re-evaluate.
        self.db.harness_versions.update_one(
            {"_id": candidate["parentVersionId"]}, {"$set": {"lifecycleStatus": "superseded"}}
        )
        self.db.harness_versions.update_one(
            {"_id": candidate_id},
            {"$set": {"lifecycleStatus": "active", "evaluationId": evaluation_id, "promotedAt": now()}},
        )
        return True

    def reject(self, candidate_id: str, evaluation_id: str, reasons: list[str]) -> None:
        self.db.harness_versions.update_one(
            {"_id": candidate_id},
            {"$set": {"lifecycleStatus": "rejected", "evaluationId": evaluation_id, "rejectionReasons": reasons}},
        )

    def rollback(self, employee_id: str, target_id: str, reason: str) -> bool:
        target = self.db.harness_versions.find_one({"_id": target_id, **self._key(employee_id)})
        if not target:
            return False
        current = self.active(employee_id)
        swapped = self.db.employees.update_one(
            {**self._key(employee_id), "activeHarnessVersionId": current["_id"]},
            {"$set": {"activeHarnessVersionId": target_id}},
        )
        if swapped.modified_count == 1:
            self.db.harness_transitions.insert_one(
                {"_id": new_id(), **self._key(employee_id), "from": current["_id"], "to": target_id,
                 "reason": reason[:200], "createdAt": now()}
            )
            return True
        return False
