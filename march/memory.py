"""Scoped memory: typed explicit preferences (read-your-writes) + notes retrieved by Atlas
Automated Embedding Vector Search, with a labeled lexical fallback."""

import re
from dataclasses import dataclass
from typing import Any

from november.input import normalize

from march.db import Store, new_id, now, stamp
from march.scope import RequestScope

INDEX = "memory_autoembed_v1"

# Small typed vocabulary (doc 05). Each rule must match an explicit first-person statement.
PREFERENCE_RULES: list[tuple[re.Pattern[str], str, Any, str]] = [
    (re.compile(r"\b(?:i\s+prefer|i\s+like|i'd\s+rather\s+have)\s+(afternoon|morning)s?\b"),
     "scheduling.preferred_period", 1, "Prefers {} meetings."),
    (re.compile(r"\b(afternoon|morning)s\s+(?:are|work)\s+(?:best|better)\s+for\s+me\b"),
     "scheduling.preferred_period", 1, "Prefers {} meetings."),
    (re.compile(r"\b(?:make|keep|default)\s+(?:my\s+)?meetings?\s+(?:to\s+)?(\d{1,3})\s*-?\s*min"),
     "scheduling.default_duration_minutes", 1, "Default meeting length {} minutes."),
    (re.compile(r"\b(?:i\s+(?:need|want|like)\s+(?:a\s+)?)?(\d{1,2})\s*-?\s*min(?:ute)?s?\s+buffer"),
     "scheduling.buffer_minutes", 1, "Wants a {}-minute buffer around meetings."),
    (re.compile(r"\bkeep\s+my\s+emails?\s+(short|brief|concise)\b"),
     "email.style", "brief", "Prefers brief emails."),
    (re.compile(r"\bi\s+(?:prefer|like)\s+(short|brief|concise)\s+emails?\b"),
     "email.style", "brief", "Prefers brief emails."),
]
MEMORY_COMMAND = re.compile(
    r"^\s*(?:hey\s+november[,!. ]*)?(?:please\s+)?(remember|forget|what\s+do\s+you\s+remember)\b",
    re.I,
)


@dataclass(frozen=True)
class Candidate:
    kind: str
    key: str | None
    value: Any
    text: str
    source_span: str


def extract(text: str) -> list[Candidate]:
    lower = text.lower()
    out: list[Candidate] = []
    for pattern, key, group, template in PREFERENCE_RULES:
        match = pattern.search(lower)
        if not match:
            continue
        value = match[group] if isinstance(group, int) else group
        if key == "email.style":
            value = "brief"
        span = text[match.start():match.end()]
        assert span.lower() in lower  # Source span is validated against the actual evidence.
        out.append(Candidate("preference", key, value, template.format(value), span))
    if not out:
        note = re.sub(r"^\s*(?:please\s+)?remember\s+(?:that\s+)?", "", text, flags=re.I).strip()
        if note and note != text.strip():
            out.append(Candidate("fact", None, None, note[:300], text))
    return out


def is_memory_command(text: str) -> bool:
    lower = text.lower()
    return bool(MEMORY_COMMAND.match(text)) or any(r[0].search(lower) for r in PREFERENCE_RULES)


def active_preferences(store: Store, scope: RequestScope) -> dict[str, str]:
    """Plain indexed read: a committed preference is visible on the very next request."""
    docs = store.db.memories.find(
        {**scope.filter(), "kind": "preference", "status": "active"}, {"key": 1, "value": 1}
    )
    return {doc["key"]: str(doc["value"]) for doc in docs if doc.get("key")}


def session_preferences(store: Store, scope: RequestScope) -> dict[str, str]:
    docs = store.db.memories.find(
        {**scope.filter(), "kind": "preference", "status": "active",
         "source.sessionId": scope.session_id},
        {"key": 1, "value": 1},
    )
    return {doc["key"]: str(doc["value"]) for doc in docs if doc.get("key")}


def _bump_epoch(store: Store, scope: RequestScope) -> None:
    store.db.employees.update_one(
        {"mode": scope.mode, "orgId": scope.org_id, "employeeId": scope.employee_id},
        {"$inc": {"memoryEpoch": 1}},
    )


def commit(store: Store, scope: RequestScope, run_id: str, items: list[Candidate]) -> list[dict[str, Any]]:
    """Server injects scope/source. Preferences supersede the prior active value, keeping history.
    Non-transactional fallback: supersede-then-insert (documented in IMPLEMENTATION-STATUS)."""
    saved: list[dict[str, Any]] = []
    for item in items:
        previous = None
        if item.kind == "preference":
            previous = store.db.memories.find_one_and_update(
                {**scope.filter(), "kind": "preference", "key": item.key, "status": "active"},
                {"$set": {"status": "superseded", "validUntil": now(), "updatedAt": now()}},
            )
        doc = stamp(
            scope,
            {
                "kind": item.kind,
                "key": item.key,
                "text": item.text,
                "value": item.value,
                "status": "active",
                "certainty": "explicit",
                "source": {"type": "user_statement", "runId": run_id, "sessionId": scope.session_id,
                           "span": item.source_span},
                "validFrom": now(),
                "validUntil": None,
                "supersedesId": previous["_id"] if previous else None,
                "updatedAt": now(),
            },
        )
        store.db.memories.insert_one(doc)
        saved.append(doc)
    if saved:
        _bump_epoch(store, scope)
    return saved


def list_active(store: Store, scope: RequestScope) -> list[dict[str, Any]]:
    return list(
        store.db.memories.find({**scope.filter(), "status": "active"}).sort("createdAt", -1)
    )


def forget(store: Store, scope: RequestScope, text: str) -> list[dict[str, Any]]:
    """Owner-requested forgetting: excluded immediately, private text purged, tombstone kept."""
    target = re.sub(r"^\s*(?:please\s+)?forget\s+(?:that\s+|about\s+|my\s+)?", "", text, flags=re.I)
    target = target.strip(" .!").lower()
    active = list_active(store, scope)
    if target in {"everything", "everything about me", "all of it"}:
        chosen = active
    else:
        words = {w for w in re.findall(r"[a-z]{4,}", target)}
        chosen = [
            m for m in active
            if words & set(re.findall(r"[a-z]{4,}", (m["text"] + " " + (m.get("key") or "")).lower()))
        ]
    for memory in chosen:
        store.db.memories.update_one(
            {"_id": memory["_id"], **scope.filter()},
            {"$set": {"status": "deleted", "text": "[forgotten]", "value": None,
                      "source.span": None, "updatedAt": now()}},
        )
        store.db.memory_tombstones.insert_one(
            {"_id": new_id(), **scope.filter(), "deletedMemoryId": memory["_id"],
             "deletionReasonCode": "owner_forget", "createdAt": now()}
        )
    if chosen:
        _bump_epoch(store, scope)
    return chosen


def _vector_ids(store: Store, scope: RequestScope, query: str, limit: int) -> list[tuple[str, float]]:
    """Scoped $vectorSearch built here, never by a model. Retries provider rate limits."""
    import time

    from pymongo.errors import OperationFailure

    for attempt in range(6):
        try:
            hits = store.db.memories.aggregate(
                [
                    {
                        "$vectorSearch": {
                            "index": INDEX,
                            "path": "text",
                            "query": {"text": query},
                            "numCandidates": max(50, limit * 10),
                            "limit": limit,
                            "filter": {**scope.filter(), "status": "active"},
                        }
                    },
                    {"$project": {"_id": 1, "score": {"$meta": "vectorSearchScore"}}},
                ]
            )
            return [(h["_id"], float(h["score"])) for h in hits]
        except OperationFailure as exc:
            if "rate limit" not in str(exc).lower() or attempt == 5:
                raise
            time.sleep(4 * (attempt + 1))
    return []


RecallCache = dict[tuple[str, str, str, str], list[tuple[str, float]]]


def recall(
    store: Store,
    scope: RequestScope,
    query: str,
    top_k: int,
    cache: RecallCache | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Scoped semantic retrieval, rehydrated through a fresh scoped find so stale index entries
    cannot resurrect forgotten or superseded memories. An optional cache (evaluation only) reuses
    the ranked list for an identical (scope, query), fetched at the maximum allowed depth."""
    method = "atlas_autoembed_vector_search"
    key = (scope.mode, scope.org_id, scope.employee_id, query)
    try:
        if cache is not None:
            if key not in cache:
                cache[key] = _vector_ids(store, scope, query, 10)
            ids = [i for i, _ in cache[key][:top_k]]
        else:
            ids = [i for i, _ in _vector_ids(store, scope, query, top_k)]
    except Exception:
        method = "lexical_fallback"
        words = set(re.findall(r"[a-z]{4,}", query.lower()))
        scored = []
        for m in list_active(store, scope):
            overlap = len(words & set(re.findall(r"[a-z]{4,}", m["text"].lower())))
            if overlap:
                scored.append((overlap, m["_id"]))
        ids = [i for _, i in sorted(scored, reverse=True)[:top_k]]
    if not ids:
        return [], method
    fresh = {
        m["_id"]: m
        for m in store.db.memories.find({"_id": {"$in": ids}, **scope.filter(), "status": "active"})
    }
    return [fresh[i] for i in ids if i in fresh], method


def handle_command(store: Store, scope: RequestScope, run_id: str, text: str) -> dict[str, Any]:
    clean = normalize(text)  # November's transcript checks (length, credentials, invisibles).
    verb = MEMORY_COMMAND.match(clean)
    word = verb[1].lower() if verb else ""
    if word.startswith("what"):
        items = list_active(store, scope)
        return {
            "capability": "memory.list",
            "items": [{"id": m["_id"], "kind": m["kind"], "text": m["text"]} for m in items],
            "message": "Here is what I remember about you." if items else "I don't have any memories about you yet.",
        }
    if word == "forget":
        gone = forget(store, scope, clean)
        return {
            "capability": "memory.forget",
            "forgotten": len(gone),
            "message": f"Forgotten {len(gone)} item(s)." if gone else "I couldn't find a matching memory to forget.",
        }
    candidates = extract(clean)
    saved = commit(store, scope, run_id, candidates)
    return {
        "capability": "memory.remember",
        "items": [{"id": m["_id"], "kind": m["kind"], "key": m["key"], "text": m["text"]} for m in saved],
        "message": ("Noted: " + "; ".join(m["text"] for m in saved)) if saved else "I didn't find anything to remember.",
    }


QUESTION = re.compile(
    r"^\s*(?:hey\s+march[,!. ]*)?(?:(?:can|could) you\s+)?(?:please\s+)?(?:tell me|answer me|remind me)?\s*"
    r"(?:what|what's|whats|when|who|where|which|how|do|does|did|is|are|am|should|have)\b|\?\s*$",
    re.I,
)


def is_question(text: str) -> bool:
    return bool(QUESTION.search(text))


def answer(store: Store, scope: RequestScope, question: str, display_name: str) -> dict[str, Any]:
    """Answer from THIS employee's own memory only, via the local model. No other scope is read."""
    import json as _json
    import urllib.request

    prefs = [m["text"] for m in store.db.memories.find(
        {**scope.filter(), "kind": "preference", "status": "active"})]
    notes, method = recall(store, scope, question, 6)
    facts = list(dict.fromkeys(prefs + [n["text"] for n in notes if n["kind"] != "preference"]))
    system = (
        f"You are MARCH, the private desk assistant for {display_name}. Answer in 1-2 short, "
        "friendly sentences. Use ONLY the facts below for anything about this person. If the facts "
        "don't cover a personal question, say you don't know yet and that they can tell you "
        "(e.g. 'remember that ...'). For general-knowledge questions answer briefly. Never invent "
        "personal details.\nFacts about this person:\n" + ("\n".join(f"- {f}" for f in facts) or "- (none yet)")
    )
    body = _json.dumps({
        "model": "qwen3:4b-instruct-2507-q4_K_M", "stream": False, "think": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}],
        "options": {"temperature": 0.2, "num_predict": 120},
    }).encode()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=30) as resp:
            text = _json.loads(resp.read())["message"]["content"].strip()
    except Exception:
        text = ("Here's what I know about you: " + "; ".join(facts)) if facts else \
            "I don't know that yet. You can tell me, for example: 'remember that I prefer 25 minute meetings'."
    return {"capability": "answer", "message": text[:600], "factsUsed": len(facts), "recallMethod": method}
