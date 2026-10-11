"""Exact-action approval: owner-bound, payload-hash-bound, single-use, fixture dispatch only."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from march.db import Store, new_id, now
from march.scope import RequestScope

APPROVAL_TTL = timedelta(minutes=5)
FIXTURE_CONNECTION = "fixture_mail"


class ApprovalRejected(PermissionError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def payload_hash(scope: RequestScope, action_type: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "actionType": action_type,
            "owner": scope.employee_id,
            "orgId": scope.org_id,
            "connectionId": FIXTURE_CONNECTION,
            "mode": scope.mode,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_mail_action(
    store: Store, scope: RequestScope, run_id: str, prepared: dict[str, Any]
) -> dict[str, Any]:
    # November's machine-readable negation decides whether a send is ever dispatchable.
    draft_only = "send" in prepared["prohibitedActions"]
    action_type = "mail.draft" if draft_only else "mail.send"
    payload = prepared["payload"]
    return store.insert_action(
        scope,
        {
            "runId": run_id,
            "connectionId": FIXTURE_CONNECTION,
            "actionType": action_type,
            "dispatchable": not draft_only,
            "normalizedPayload": payload,
            "payloadHash": payload_hash(scope, action_type, payload),
            "constraints": prepared["constraints"],
            "prohibitedActions": prepared["prohibitedActions"],
            "state": "draft" if draft_only else "pending",
            "expiresAt": now() + APPROVAL_TTL,
            "approval": None,
            "idempotencyKey": new_id(),
        },
    )


def edit_payload(
    store: Store, scope: RequestScope, action_id: str, changes: dict[str, Any]
) -> dict[str, Any]:
    """Any edit produces a new hash and discards prior approval; it must be re-approved."""
    action = store.get_action(scope, action_id)
    if action["state"] not in {"pending", "draft"}:
        raise ApprovalRejected("not_editable")
    payload = dict(action["normalizedPayload"])
    for key in ("to", "subject", "body"):
        if key in changes:
            payload[key] = changes[key]
    updated = store.transition_action(
        scope,
        action_id,
        {"payloadHash": action["payloadHash"], "state": action["state"]},
        {
            "normalizedPayload": payload,
            "payloadHash": payload_hash(scope, action["actionType"], payload),
            "approval": None,
            "expiresAt": now() + APPROVAL_TTL,
        },
    )
    if updated is None:
        raise ApprovalRejected("concurrent_change")
    return updated


def approve(
    store: Store,
    scope: RequestScope,
    action_id: str,
    displayed_hash: str,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Owner approval of the exact displayed payload; dispatches once to the fixture outbox."""
    current = at or now()
    action = store.get_action(scope, action_id)  # Another employee's action is simply not found.
    if not action["dispatchable"] or "send" in action["prohibitedActions"]:
        raise ApprovalRejected("draft_only_not_sendable")
    if action["state"] != "pending":
        raise ApprovalRejected(f"state_{action['state']}")
    if displayed_hash != action["payloadHash"]:
        raise ApprovalRejected("payload_changed")
    expires = action["expiresAt"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=current.tzinfo)
    if current >= expires:
        store.transition_action(scope, action_id, {"state": "pending"}, {"state": "expired"})
        raise ApprovalRejected("expired")
    attempt = new_id()
    claimed = store.transition_action(
        scope,
        action_id,
        {"state": "pending", "payloadHash": displayed_hash},
        {
            "state": "executing",
            "executionAttemptId": attempt,
            "approval": {
                "principalId": scope.employee_id,
                "principalSource": scope.identity_source,
                "approvedAt": current,
                "approvedPayloadHash": displayed_hash,
            },
        },
    )
    if claimed is None:
        raise ApprovalRejected("already_claimed")
    receipt = store.record_simulated_send(
        scope,
        {
            "actionId": action_id,
            "executionAttemptId": attempt,
            "payloadHash": displayed_hash,
            "to": claimed["normalizedPayload"]["to"],
            "subject": claimed["normalizedPayload"]["subject"],
            "label": "SIMULATED fixture send; no email was delivered",
        },
    )
    done = store.transition_action(
        scope,
        action_id,
        {"state": "executing", "executionAttemptId": attempt},
        {"state": "simulated_sent", "providerResult": {"receiptId": receipt["_id"]}},
    )
    assert done is not None
    return done


def reject(store: Store, scope: RequestScope, action_id: str) -> dict[str, Any]:
    updated = store.transition_action(
        scope, action_id, {"state": {"$in": ["pending", "draft"]}}, {"state": "rejected"}
    )
    if updated is None:
        raise ApprovalRejected("not_rejectable")
    return updated
