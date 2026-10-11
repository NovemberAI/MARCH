"""MongoDB access. Typed, scope-filtered repository methods only; no caller-built queries."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.database import Database

from march.config import Settings
from march.scope import RequestScope, ScopeError

SCHEMA_VERSION = 1


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


def connect(cfg: Settings, mode: str) -> Database[Any]:
    if not cfg.atlas_configured:
        raise RuntimeError("MONGODB_URI is not configured")
    client: MongoClient[Any] = MongoClient(
        cfg.mongodb_uri, appname="march", serverSelectionTimeoutMS=8000, tz_aware=True
    )
    return client[cfg.db_name(mode)]


def ensure_indexes(db: Database[Any]) -> None:
    scope = [("mode", ASCENDING), ("orgId", ASCENDING), ("employeeId", ASCENDING)]
    db.employees.create_index(scope, unique=True)
    db.sessions.create_index(scope + [("lastActiveAt", DESCENDING)])
    db.runs.create_index(scope + [("createdAt", DESCENDING)])
    db.pending_actions.create_index(scope + [("idempotencyKey", ASCENDING)], unique=True)
    db.pending_actions.create_index([("state", ASCENDING), ("expiresAt", ASCENDING)])
    db.fixture_items.create_index(
        scope + [("kind", ASCENDING), ("externalId", ASCENDING)], unique=True
    )
    db.memories.create_index(
        scope + [("status", ASCENDING), ("kind", ASCENDING), ("updatedAt", DESCENDING)]
    )
    db.simulated_sends.create_index(scope + [("actionId", ASCENDING)], unique=True)


def stamp(scope: RequestScope, doc: dict[str, Any]) -> dict[str, Any]:
    """Scope fields are always taken from the server scope, overriding anything in doc."""
    out = {"_id": new_id(), "schemaVersion": SCHEMA_VERSION, "createdAt": now()}
    out.update(doc)
    out.update(scope.filter())
    return out


class Store:
    """Every read and write is constrained by a RequestScope supplied by the server."""

    def __init__(self, db: Database[Any]) -> None:
        self.db = db

    # --- sessions (trusted construction only) ---
    def open_session(self, mode: str, org_id: str, employee_id: str, source: str) -> RequestScope:
        session_id = new_id()
        scope = RequestScope(mode, org_id, employee_id, session_id, source)
        self.db.sessions.insert_one(
            {
                "_id": session_id,
                "schemaVersion": SCHEMA_VERSION,
                **scope.filter(),
                "identitySource": source,
                "state": "active",
                "createdAt": now(),
                "lastActiveAt": now(),
            }
        )
        return scope

    def resume_session(self, session_id: str) -> RequestScope:
        doc = self.db.sessions.find_one({"_id": session_id, "state": "active"})
        if not doc:
            raise ScopeError("no active session")
        self.db.sessions.update_one({"_id": session_id}, {"$set": {"lastActiveAt": now()}})
        return RequestScope(
            doc["mode"], doc["orgId"], doc["employeeId"], session_id, doc["identitySource"]
        )

    # --- employees ---
    def employee(self, scope: RequestScope) -> dict[str, Any]:
        doc = self.db.employees.find_one(scope.filter())
        if not doc:
            raise ScopeError("employee not found")
        return doc

    # --- fixture items ---
    def fixture_items(self, scope: RequestScope, kind: str) -> list[dict[str, Any]]:
        return list(self.db.fixture_items.find({**scope.filter(), "kind": kind}))

    # --- runs ---
    def insert_run(self, scope: RequestScope, doc: dict[str, Any]) -> dict[str, Any]:
        run = stamp(scope, {"sessionId": scope.session_id, **doc})
        self.db.runs.insert_one(run)
        return run

    def update_run(self, scope: RequestScope, run_id: str, fields: dict[str, Any]) -> None:
        self.db.runs.update_one({"_id": run_id, **scope.filter()}, {"$set": fields})

    def get_run(self, scope: RequestScope, run_id: str) -> dict[str, Any]:
        doc = self.db.runs.find_one({"_id": run_id, **scope.filter()})
        if not doc:
            raise ScopeError("run not found")
        return doc

    def recent_runs(self, scope: RequestScope, limit: int = 10) -> list[dict[str, Any]]:
        return list(self.db.runs.find(scope.filter()).sort("createdAt", -1).limit(limit))

    # --- pending actions ---
    def insert_action(self, scope: RequestScope, doc: dict[str, Any]) -> dict[str, Any]:
        action = stamp(scope, doc)
        self.db.pending_actions.insert_one(action)
        return action

    def get_action(self, scope: RequestScope, action_id: str) -> dict[str, Any]:
        doc = self.db.pending_actions.find_one({"_id": action_id, **scope.filter()})
        if not doc:
            raise ScopeError("action not found")
        return doc

    def list_actions(self, scope: RequestScope, states: list[str]) -> list[dict[str, Any]]:
        query = {**scope.filter(), "state": {"$in": states}}
        return list(self.db.pending_actions.find(query).sort("createdAt", -1))

    def transition_action(
        self,
        scope: RequestScope,
        action_id: str,
        expect: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Atomic compare-and-set: only succeeds if the scoped doc still matches `expect`."""
        return self.db.pending_actions.find_one_and_update(
            {"_id": action_id, **scope.filter(), **expect},
            {"$set": {**fields, "updatedAt": now()}},
            return_document=ReturnDocument.AFTER,
        )

    def record_simulated_send(self, scope: RequestScope, doc: dict[str, Any]) -> dict[str, Any]:
        receipt = stamp(scope, doc)
        self.db.simulated_sends.insert_one(receipt)
        return receipt

    def simulated_sends(self, scope: RequestScope) -> list[dict[str, Any]]:
        return list(self.db.simulated_sends.find(scope.filter()))
