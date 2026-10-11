"""Employee-scoped fixture tools. They read only the caller's own fixture items."""

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from march.db import Store
from march.scope import RequestScope

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MAIL_WORDS = re.compile(
    r"\b(?:e-?mail|mail|message|note to|write to|send (?:it|this|that|the (?:draft|note)))\b"
    r"|[\w.+-]+(?:@|\s+at\s+)[\w-]+(?:\.|\s+dot\s+)(?:com|org|net|io|edu)\b",
    re.I,
)
CAL_WORDS = re.compile(r"\b(?:slot|meeting|meet|schedule|calendar|availability|free time)\b", re.I)


DOMAIN = re.compile(r"\b((?:https?://)?(?:[a-z0-9-]+\.)+(?:com|org|net|io|ai|edu|gov|dev|app|co))\b(/\S*)?", re.I)
OPEN_SITE = re.compile(r"\b(?:open|visit|go to|navigate to|pull up|load|browse to|take me to)\b", re.I)
WEB_WORDS = re.compile(r"\b(?:website|web page|webpage|on the web|google|look up|search for)\b", re.I)


def browser_targets(command: str) -> list[str]:
    urls = []
    for m in DOMAIN.finditer(command):
        if re.search(r"(?:@|\s+at)\s*$", command[:m.start()]):
            continue  # Part of an email address, not a site to open.
        host = m[1] if m[1].lower().startswith("http") else "https://" + m[1].lower()
        urls.append(host + (m[2] or ""))
    return urls


def wants_browser(command: str) -> bool:
    return bool(OPEN_SITE.search(command) and browser_targets(command)) or bool(WEB_WORDS.search(command))


def route(compiled: dict[str, Any]) -> str:
    """Map November's validated intent to a MARCH capability. Never loosens November policy."""
    status = compiled["decision"]["status"]
    if status in {"cancelled", "clarify"}:
        return status
    command = compiled["normalizedCommand"]
    if wants_browser(command):
        return "browser.research"
    if MAIL_WORDS.search(command) and compiled["intent"]["intent_type"] not in {"cancel", "clarify"}:
        return "mail.prepare"  # November's policy decision is kept; send still needs approval.
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


def _edit1(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) <= 1
    short, long = (a, b) if len(a) < len(b) else (b, a)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


def _match_contact(words: list[str], contacts: dict[str, Any]) -> tuple[Any, str | None]:
    for w in words:
        if w.casefold() in contacts:
            return contacts[w.casefold()], None
    for w in words:  # Speech-to-text slips such as "Bend" for "Ben": one edit, own book only.
        if len(w) >= 3:
            close = [c for name, c in contacts.items() if _edit1(w.casefold(), name)]
            if len(close) == 1:
                return close[0], w
    return None, None


def _last_draft(store: Store, scope: RequestScope) -> Any:
    """Most recent prepared email in this employee's current session (insertion order)."""
    runs = store.db.runs.find(
        {**scope.filter(), "sessionId": scope.session_id, "capability": "mail.prepare",
         "result.status": "prepared"}
    ).sort("$natural", -1).limit(1)
    for run in runs:
        return run["result"]["payload"]
    return None


def prepare_mail(
    store: Store,
    scope: RequestScope,
    compiled: dict[str, Any],
    config: dict[str, Any],
    prefs: dict[str, str],
) -> dict[str, Any]:
    intent = compiled["intent"]
    command = compiled["normalizedCommand"]
    contacts = {
        item["payload"]["name"].casefold(): item["payload"]
        for item in store.fixture_items(scope, "contact")
    }
    words = [w for e in intent["entities"] for w in re.findall(r"[A-Za-z]+", e)]
    words += re.findall(r"\b(?:to|email|e-mail|message)\s+([A-Za-z]+)", command, re.I)
    if re.search(r"[\w.+-]+(?:@|\s+at\s+)[\w-]+(?:\.|\s+dot\s+)\w+", command, re.I):
        names = ", ".join(c["name"] for c in contacts.values())
        return {
            "capability": "mail.prepare",
            "status": "clarify",
            "message": f"This demo only emails fictional contacts in your own address book ({names}); "
            "it never sends to real addresses.",
        }
    recipient, heard_as = _match_contact(words, contacts)
    if recipient is None:
        previous = _last_draft(store, scope)
        if previous is not None:  # Follow-up in the same session ("the email should say ...").
            recipient = next((c for c in contacts.values() if c["email"] in previous["to"]), None)
    if recipient is None:
        names = ", ".join(c["name"] for c in contacts.values())
        return {
            "capability": "mail.prepare",
            "status": "clarify",
            "message": f"Who should receive it? Your address book has: {names}.",
        }
    employee = store.employee(scope)
    topic = _topic(compiled["normalizedCommand"], intent["entities"])
    brief = config["applyPreferences"] and prefs.get("email.style") == "brief"
    first = recipient["name"].split()[0]
    said = re.search(
        r"\b(?:saying|say|says|tell (?:him|her|them)|to say|that says|asking)\s+(?:that\s+)?(.+?)[.!?]?$",
        command, re.I)
    sentences = [f"I wanted to follow up about {topic}."]
    if said:
        ask = said[1].strip()
        ask = re.sub(r"^what's\b", "what's", ask)
        sentences = [ask[:1].upper() + ask[1:] + ("?" if re.match(r"(?i)(what|how|when|where|who|can|could|is|are|do|does)\b", ask) else ".")]
    if not brief and not said:
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
        "heardAs": heard_as,
        "prohibitedActions": list(intent["prohibited_actions"]),
        "constraints": list(intent["constraints"]),
    }
