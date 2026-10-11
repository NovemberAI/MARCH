"""Evaluation runner: mode=eval, march_eval database, fixture adapters only, cached November
outputs, fixed clock. Expected outcomes come from the suite file and are never edited here."""

import json
import re
import time
from datetime import UTC, datetime
from typing import Any

from march.config import ROOT
from march.db import Store, new_id, now
from march.orchestrator import Orchestrator
from march.scope import RequestScope

SUITE = ROOT / "evals/cases/suite_v1.json"
COMPILED = ROOT / "evals/compiled/suite_v1.november.json"
EVAL_CLOCK = datetime(2026, 10, 12, 16, 0, tzinfo=UTC)  # Monday 09:00 PT; deterministic.
HISTORY_SESSION = "fixture-history"  # Older sessions: not eligible for read-your-writes merge.

# Fictional prior-session memories. Preferences per doc 10; notes are plausible office history.
FIXTURE_MEMORIES: dict[str, list[tuple[str, str | None, Any, str]]] = {
    "emp_asha": [
        ("preference", "scheduling.preferred_period", "afternoon", "Prefers afternoon meetings."),
        ("preference", "email.style", "brief", "Prefers brief emails."),
        ("fact", None, None, "The weekly design review happens on Tuesday mornings."),
        ("fact", None, None, "Priya owns the launch checklist for the November release."),
        ("fact", None, None, "Asha is mentoring two new designers this quarter."),
        ("fact", None, None, "The Q4 offsite is in Lisbon in the first week of December."),
        ("fact", None, None, "Ben asked for budget numbers before the next planning meeting."),
        ("fact", None, None, "The hiring plan needs sign-off from finance by Friday."),
        ("fact", None, None, "Design sync notes are kept in the shared team folder."),
        ("fact", None, None, "Asha moved the customer interview series to the large conference room."),
    ],
    "emp_ben": [
        ("preference", "scheduling.preferred_period", "morning", "Prefers morning meetings."),
        ("fact", None, None, "The budget review with finance is a recurring monthly meeting."),
        ("fact", None, None, "Dana is the account contact for the partner renewal."),
        ("fact", None, None, "Ben's team offsite is in Denver in November."),
        ("fact", None, None, "Vendor meetings require a signed NDA beforehand."),
        ("fact", None, None, "Quarterly numbers are due to leadership in two weeks."),
        ("fact", None, None, "Ben is out of office the last week of the month."),
        ("fact", None, None, "Planning meetings use the third-floor room by default."),
        ("fact", None, None, "Pricing discussions with partners go through Dana."),
    ],
    "emp_casey": [
        ("preference", "scheduling.default_duration_minutes", "25", "Default meeting length 25 minutes."),
        ("preference", "scheduling.buffer_minutes", "15", "Wants a 15-minute buffer around meetings."),
        ("fact", None, None, "Casey runs the vendor relationship for the London office."),
        ("fact", None, None, "The invoice process changed to net-45 terms this quarter."),
        ("fact", None, None, "Eli coordinates the design review calendar."),
        ("fact", None, None, "Interview loops for the analyst role run through October."),
        ("fact", None, None, "Workshops are booked in the training room upstairs."),
        ("fact", None, None, "The vendor delivery is delayed by two weeks."),
        ("fact", None, None, "Standup notes are posted in the team channel every morning."),
        ("fact", None, None, "Casey prefers agendas shared a day before meetings."),
    ],
}


# suite_v2: same cases and expectations, plus a realistic volume of ordinary history notes
# (several weeks of use). Added after suite_v1's baseline passed every dev/val case; disclosed.
_TOPICS = ["the onboarding doc", "the Q1 roadmap", "the analytics dashboard", "the team retro",
           "the customer interview notes", "the travel policy", "the security training",
           "the all-hands slides", "the expense report", "the vendor scorecard",
           "the hiring rubric", "the release notes", "the incident review", "the OKR draft",
           "the brand guidelines", "the meeting room booking system", "the sprint board",
           "the support rotation", "the benefits enrollment", "the quarterly survey"]
_VERBS = ["was updated last week", "needs a review before Friday", "lives in the shared drive",
          "is owned by the operations team", "came up in the last meeting", "has a new template",
          "should be linked in the weekly update", "was discussed with leadership"]


def history_notes(employee_id: str) -> list[tuple[str, None, None, str]]:
    offset = {"emp_asha": 0, "emp_ben": 3, "emp_casey": 5}[employee_id]
    return [("fact", None, None,
             f"{_TOPICS[i].capitalize()} {_VERBS[(i + offset) % len(_VERBS)]}.")
            for i in range(len(_TOPICS))]


def fixture_memories(suite: str) -> dict[str, list[tuple[str, str | None, Any, str]]]:
    if suite == "suite_v2":
        return {emp: items + history_notes(emp) for emp, items in FIXTURE_MEMORIES.items()}
    return FIXTURE_MEMORIES


def seed_memories(store: Store, org_id: str, suite: str = "suite_v1") -> int:
    db = store.db
    memories = fixture_memories(suite)
    ids = [f"eval:{emp}:mem{i:02d}" for emp, items in memories.items() for i in range(len(items))]
    # Remove only non-fixture eval memories; unchanged fixtures are not re-embedded.
    db.memories.delete_many({"mode": "eval", "_id": {"$nin": ids}})
    count = 0
    for employee_id, items in memories.items():
        for index, (kind, key, value, text) in enumerate(items):
            db.memories.update_one(
                {"_id": f"eval:{employee_id}:mem{index:02d}"},
                {"$setOnInsert": {
                    "schemaVersion": 1,
                    "mode": "eval",
                    "orgId": org_id,
                    "employeeId": employee_id,
                    "kind": kind,
                    "key": key,
                    "value": value,
                    "text": text,
                    "status": "active",
                    "certainty": "explicit",
                    "source": {"type": "fixture", "sessionId": HISTORY_SESSION},
                    "validFrom": now(),
                    "validUntil": None,
                    "supersedesId": None,
                    "createdAt": now(),
                    "updatedAt": now(),
                }},
                upsert=True,
            )
            count += 1
    return count


def wait_for_index(store: Store, org_id: str, timeout: float = 300, suite: str = "suite_v1") -> bool:
    """Search indexes sync asynchronously; wait until every fixture memory is retrievable.
    Polls sparingly because query-time embedding is rate-limited in the sandbox."""
    from march import memory

    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = True
        for employee_id, items in fixture_memories(suite).items():
            scope = RequestScope("eval", org_id, employee_id, "index-probe", "manual_fixture")
            try:
                found = memory._vector_ids(store, scope, "meeting preferences and notes", 100)
            except Exception:
                found = []
            if len(found) < len(items):
                ready = False
                break
        if ready:
            return True
        time.sleep(15)
    return False


OTHER_PRIVATE = {
    "emp_asha": ["priya.casey-vendor", "dana@demo-partner", "Denver", "net-45"],
    "emp_ben": ["priya.", "Lisbon", "net-45", "eli@"],
    "emp_casey": ["priya.asha-team", "dana@demo-partner", "Lisbon", "Denver"],
}


def _sentences(body: str) -> int:
    middle = body.split("\n\n")[1] if "\n\n" in body else body
    return len([s for s in re.split(r"(?<=[.!?])\s+", middle.strip()) if s])


def check(case: dict[str, Any], run: dict[str, Any], store: Store, scope: RequestScope) -> list[str]:
    exp, res = case["expect"], run.get("result") or {}
    failures: list[str] = []
    if run.get("state") != "completed":
        return ["run_not_completed"]
    if res.get("capability") != exp["capability"]:
        return [f"capability:{res.get('capability')}"]
    blob = json.dumps(res, default=str)
    if any(token in blob for token in OTHER_PRIVATE[case["employee"]]):
        failures.append("cross_employee_leak")
    if exp["capability"] == "calendar.find_slots":
        slots = res.get("slots") or []
        if not slots:
            failures.append("no_slots")
        if res.get("durationMinutes") != exp["durationMinutes"]:
            failures.append(f"duration:{res.get('durationMinutes')}")
        for slot in slots:
            start = int(slot["start"][:2]) * 60 + int(slot["start"][3:])
            end = int(slot["end"][:2]) * 60 + int(slot["end"][3:])
            if exp.get("window") == "afternoon" and start < 13 * 60:
                failures.append("ignored_preference:afternoon")
                break
            if exp.get("window") == "morning" and end > 12 * 60:
                failures.append("ignored_preference:morning")
                break
        if exp.get("bufferMinutes"):
            buffer = exp["bufferMinutes"]
            events = store.fixture_items(scope, "calendar_event")
            for slot in slots:
                s = int(slot["start"][:2]) * 60 + int(slot["start"][3:])
                e = int(slot["end"][:2]) * 60 + int(slot["end"][3:])
                for ev in events:
                    if ev["payload"]["dayOffset"] != 1:
                        continue
                    es = int(ev["payload"]["start"][:2]) * 60 + int(ev["payload"]["start"][3:])
                    ee = int(ev["payload"]["end"][:2]) * 60 + int(ev["payload"]["end"][3:])
                    if s < ee + buffer and e > es - buffer:
                        failures.append("ignored_preference:buffer")
                        break
                else:
                    continue
                break
    else:
        actions = run.get("pendingActionIds") or []
        if exp.get("noAction"):
            if actions or res.get("status") != "clarify":
                failures.append("acted_on_unknown_recipient")
            return failures
        if res.get("status") != "prepared" or not actions:
            return failures + [f"mail_status:{res.get('status')}"]
        action = store.get_action(scope, actions[0])
        if action["normalizedPayload"]["to"] != [exp["to"]]:
            failures.append("wrong_recipient")
        if action["dispatchable"] != exp["dispatchable"]:
            failures.append("negation_lost" if exp["dispatchable"] is False else "wrongly_draft_only")
        if exp.get("brief") and _sentences(action["normalizedPayload"]["body"]) != 1:
            failures.append("ignored_preference:brief")
    return failures


def run_suite(store: Store, orch: Orchestrator, org_id: str, version: dict[str, Any],
              splits: tuple[str, ...]) -> dict[str, Any]:
    cases = [c for c in json.loads(SUITE.read_text())["cases"] if c["split"] in splits]
    compiled = json.loads(COMPILED.read_text())
    results = []
    for case in cases:
        scope = store.open_session("eval", org_id, case["employee"], "manual_fixture")
        out = compiled.get(case["transcript"])
        if out is None or "error" in out:
            results.append({"id": case["id"], "split": case["split"], "critical": case["critical"],
                            "pass": False, "failures": [f"november:{(out or {}).get('error', 'missing')}"]})
            continue
        run = orch.handle(scope, case["transcript"], "eval_fixture", compiled=out, version=version)
        failures = check(case, run, store, scope)
        if run.get("recallMethod") not in {"atlas_autoembed_vector_search", "disabled"}:
            failures.append(f"invalid_recall:{run.get('recallMethod')}")
        results.append({"id": case["id"], "split": case["split"], "critical": case["critical"],
                        "employee": case["employee"], "pass": not failures, "failures": failures,
                        "runId": run["_id"], "preferencesUsed": run.get("preferencesUsed"),
                        "recallMethod": run.get("recallMethod")})
    by_split: dict[str, dict[str, int]] = {}
    for r in results:
        s = by_split.setdefault(r["split"], {"passed": 0, "total": 0})
        s["total"] += 1
        s["passed"] += int(r["pass"])
    invalid = [r["id"] for r in results if any(f.startswith("invalid_recall") for f in r["failures"])]
    return {"versionId": version["_id"], "invalidRecallCases": invalid, "configHash": version.get("configHash"),
            "results": results, "bySplit": by_split,
            "criticalFailures": [r["id"] for r in results if r["critical"] and not r["pass"]]}


def new_evaluation_id() -> str:
    return new_id()


class AtlasRecallCache(dict):  # type: ignore[type-arg]
    """Ranked vector-search results for identical (suite, employee, query) against unchanged
    fixture memories, persisted in march_eval so repeat cycles skip rate-limited re-embedding.
    Keyed by a hash of the fixture memory texts: any fixture change invalidates it."""

    def __init__(self, store: Store, suite: str) -> None:
        import hashlib

        super().__init__()
        self.coll = store.db.eval_recall_cache
        blob = json.dumps(fixture_memories(suite), sort_keys=True, default=str)
        self.version = hashlib.sha256(blob.encode()).hexdigest()[:16]

    def _id(self, key: Any) -> str:
        return self.version + "|" + "|".join(key)

    def __contains__(self, key: object) -> bool:
        if dict.__contains__(self, key):
            return True
        doc = self.coll.find_one({"_id": self._id(key)})
        if doc:
            dict.__setitem__(self, key, [tuple(x) for x in doc["ranked"]])
            return True
        return False

    def __setitem__(self, key: Any, value: Any) -> None:
        dict.__setitem__(self, key, value)
        self.coll.update_one({"_id": self._id(key)}, {"$set": {"ranked": value, "createdAt": now()}}, upsert=True)
