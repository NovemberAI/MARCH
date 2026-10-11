"""Employee-scoped fixture tools. They read only the caller's own fixture items."""

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from march.db import Store
from march.scope import RequestScope

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MAIL_WORDS = re.compile(r"\b(?:e-?mail|mail|message|note to|write to)\b", re.I)
CAL_WORDS = re.compile(r"\b(?:slot|meeting|meet|schedule|calendar|availability|free time)\b", re.I)


def route(compiled: dict[str, Any]) -> str:
    """Map November's validated intent to a MARCH capability. Never loosens November policy."""
    status = compiled["decision"]["status"]
    if status in {"cancelled", "clarify"}:
        return status
    command = compiled["normalizedCommand"]
    if MAIL_WORDS.search(command) and compiled["intent"]["intent_type"] in {
        "draft",
        "prepare",
        "execute",
    }:
        return "mail.prepare"
    if CAL_WORDS.search(command):
        return "calendar.find_slots"
    if compiled["intent"]["intent_type"] in {"research", "navigate"} and not MAIL_WORDS.search(command):
        return "browser.research"
    return "unsupported"


def _target_day(command: str, today: date) -> tuple[date, str]:
    lower = command.lower()
    if "today" in lower:
        return today, "today"
    for index, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}\b", lower):
            ahead = (index - today.weekday()) % 7 or 7
            return today + timedelta(days=ahead), name.capitalize()
    return today + timedelta(days=1), "tomorrow"


def _duration(command: str, default: int) -> tuple[int, bool]:
    match = re.search(r"(\d{1,3})\s*-?\s*min", command, re.I)
    if match:
        return max(5, min(240, int(match[1]))), True
    if re.search(r"\b(?:an|one|1)\s+hour\b", command, re.I):
        return 60, True
    return default, False


def _hm(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def find_slots(
    store: Store,
    scope: RequestScope,
    command: str,
    config: dict[str, Any],
    prefs: dict[str, str],
    now: datetime,
) -> dict[str, Any]:
    employee = store.employee(scope)
    tz = ZoneInfo(employee["timeZone"])
    today = now.astimezone(tz).date()
    day, day_label = _target_day(command, today)
    explicit_default = prefs.get("scheduling.default_duration_minutes")
    default = int(explicit_default) if explicit_default else int(config["defaultMeetingMinutes"])
    duration, stated = _duration(command, default)
    start, end = config["workdayStartHour"] * 60, config["workdayEndHour"] * 60
    applied: list[str] = []
    period = prefs.get("scheduling.preferred_period")
    if config["applyPreferences"] and period == "afternoon":
        start = max(start, 13 * 60)
        applied.append("scheduling.preferred_period=afternoon")
    elif config["applyPreferences"] and period == "morning":
        end = min(end, 12 * 60)
        applied.append("scheduling.preferred_period=morning")
    buffer = int(prefs.get("scheduling.buffer_minutes", "0")) if config["applyPreferences"] else 0
    if buffer:
        applied.append(f"scheduling.buffer_minutes={buffer}")
    if explicit_default and not stated and config["applyPreferences"]:
        applied.append(f"scheduling.default_duration_minutes={explicit_default}")
    offset = (day - today).days
    busy = sorted(
        (_hm(item["payload"]["start"]) - buffer, _hm(item["payload"]["end"]) + buffer)
        for item in store.fixture_items(scope, "calendar_event")
        if item["payload"]["dayOffset"] == offset
    )
    slots: list[dict[str, str]] = []
    cursor = start
    step = int(config["slotStepMinutes"])
    while cursor + duration <= end and len(slots) < int(config["maxSlots"]):
        if all(cursor + duration <= b_start or cursor >= b_end for b_start, b_end in busy):
            slots.append({"start": _fmt(cursor), "end": _fmt(cursor + duration)})
            cursor += duration
        else:
            cursor += step
    return {
        "capability": "calendar.find_slots",
        "date": day.isoformat(),
        "dayLabel": day_label,
        "timeZone": employee["timeZone"],
        "durationMinutes": duration,
        "slots": slots,
        "appliedPreferences": applied,
        "note": "Only your own fixture calendar was read; other attendees' calendars are private.",
    }


def _topic(command: str, entities: list[str]) -> str:
    match = re.search(r"\babout\s+(.+?)(?:,|\.|\bbut\b|\band do\b|$)", command, re.I)
    if match:
        return match[1].strip()
    return "a quick follow-up"


def prepare_mail(
    store: Store,
    scope: RequestScope,
    compiled: dict[str, Any],
    config: dict[str, Any],
    prefs: dict[str, str],
) -> dict[str, Any]:
    intent = compiled["intent"]
    contacts = {
        item["payload"]["name"].casefold(): item["payload"]
        for item in store.fixture_items(scope, "contact")
    }
    recipient = next(
        (contacts[e.casefold()] for e in intent["entities"] if e.casefold() in contacts), None
    )
    if recipient is None:
        return {
            "capability": "mail.prepare",
            "status": "clarify",
            "message": "Who should receive it? I only use contacts in your own address book.",
        }
    employee = store.employee(scope)
    topic = _topic(compiled["normalizedCommand"], intent["entities"])
    brief = config["applyPreferences"] and prefs.get("email.style") == "brief"
    first = recipient["name"].split()[0]
    sentences = [f"I wanted to follow up about {topic}."]
    if not brief:
        sentences += [
            "Let me know if you have any questions or need anything from me.",
            "Happy to find a time to discuss.",
        ]
    sentences = sentences[: int(config["emailMaxSentences"])]
    body = f"{config['emailGreeting']} {first},\n\n{' '.join(sentences)}\n\n"
    body += f"{config['emailSignoff']},\n{employee['displayName']}"
    return {
        "capability": "mail.prepare",
        "status": "prepared",
        "payload": {
            "from": employee["fixtureEmail"],
            "to": [recipient["email"]],
            "subject": topic[:1].upper() + topic[1:],
            "body": body,
        },
        "appliedPreferences": ["email.style=brief"] if brief else [],
        "prohibitedActions": list(intent["prohibited_actions"]),
        "constraints": list(intent["constraints"]),
    }
