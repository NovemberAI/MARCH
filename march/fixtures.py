"""Fictional demo employees and fixture items. No real people, accounts or addresses."""

from typing import Any

from pymongo.database import Database

from march.db import SCHEMA_VERSION, ensure_indexes, now

FIXTURE_VERSION = 1

EMPLOYEES = [
    {
        "employeeId": "emp_asha",
        "displayName": "Asha (fictional)",
        "timeZone": "America/Los_Angeles",
        "fixtureEmail": "asha@demo-office.example",
    },
    {
        "employeeId": "emp_ben",
        "displayName": "Ben (fictional)",
        "timeZone": "America/New_York",
        "fixtureEmail": "ben@demo-office.example",
    },
    {
        "employeeId": "emp_casey",
        "displayName": "Casey (fictional)",
        "timeZone": "Europe/London",
        "fixtureEmail": "casey@demo-office.example",
    },
]

# dayOffset is relative to "today" in the employee's own timezone.
CALENDARS = {
    "emp_asha": [(1, "09:00", "10:00", "Design review"), (1, "13:00", "14:00", "Lunch & learn")],
    "emp_ben": [(1, "09:30", "11:00", "Budget sync"), (1, "15:00", "15:30", "1:1")],
    "emp_casey": [(1, "10:00", "10:30", "Standup"), (1, "14:00", "15:00", "Vendor call")],
}

CONTACTS = {
    "emp_asha": [("Priya", "priya.asha-team@demo-office.example"), ("Ben", "ben@demo-office.example")],
    "emp_ben": [("Dana", "dana@demo-partner.example"), ("Asha", "asha@demo-office.example")],
    "emp_casey": [("Priya", "priya.casey-vendor@demo-partner.example"), ("Eli", "eli@demo-office.example")],
}


def seed(db: Database[Any], mode: str, org_id: str) -> dict[str, int]:
    ensure_indexes(db)
    counts = {"employees": 0, "fixture_items": 0}
    for employee in EMPLOYEES:
        key = {"mode": mode, "orgId": org_id, "employeeId": employee["employeeId"]}
        db.employees.update_one(
            key,
            {
                "$set": {**employee, "enabled": True, "fixture": True, "updatedAt": now()},
                "$setOnInsert": {
                    "_id": f"{mode}:{employee['employeeId']}",
                    "schemaVersion": SCHEMA_VERSION,
                    "memoryEpoch": 0,
                    "activeHarnessVersionId": None,
                    "consent": {"voiceEnrollment": False, "audioCloudTransfer": False},
                    "createdAt": now(),
                },
            },
            upsert=True,
        )
        counts["employees"] += 1
        items: list[tuple[str, str, dict[str, Any]]] = []
        for index, (offset, start, end, title) in enumerate(CALENDARS[employee["employeeId"]]):
            items.append(
                (
                    "calendar_event",
                    f"evt_{index}",
                    {"dayOffset": offset, "start": start, "end": end, "title": title},
                )
            )
        for name, email in CONTACTS[employee["employeeId"]]:
            items.append(("contact", f"contact_{name.lower()}", {"name": name, "email": email}))
        for kind, external_id, payload in items:
            db.fixture_items.update_one(
                {**key, "kind": kind, "externalId": external_id},
                {
                    "$set": {"payload": payload, "fixtureVersion": FIXTURE_VERSION},
                    "$setOnInsert": {
                        "_id": f"{mode}:{employee['employeeId']}:{kind}:{external_id}",
                        "schemaVersion": SCHEMA_VERSION,
                        "createdAt": now(),
                    },
                },
                upsert=True,
            )
            counts["fixture_items"] += 1
    return counts
