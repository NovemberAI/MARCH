"""One request: November compile -> MARCH scope -> scoped fixture tool -> run + pending action."""

import os
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from march import actions, browser, memory, telemetry, tools
from march.db import Store, now
from march.harness import TOOL_CONSTANTS, Harness
from march.november_bridge import COMPILE_ERRORS, IntentSource
from march.scope import RequestScope


class Orchestrator:
    def __init__(
        self,
        store: Store,
        compiler: IntentSource,
        clock: Callable[[], datetime] = now,
        recall_cache: memory.RecallCache | None = None,
    ) -> None:
        self.store = store
        self.compiler = compiler
        self.clock = clock
        self.recall_cache = recall_cache  # Evaluation only.

    def version_for(self, scope: RequestScope) -> dict[str, Any]:
        return Harness(self.store.db, scope.mode, scope.org_id).active(scope.employee_id)

    def select_context(
        self, scope: RequestScope, query: str, capability: str, config: dict[str, Any]
    ) -> tuple[dict[str, str], list[dict[str, Any]], str]:
        """Deterministic context assembly governed by the harness retrieval policy."""
        retrieval, workflow = config["retrieval"], config["workflow"]
        recalled, method = memory.recall(
            self.store, scope, query, int(retrieval["semanticTopK"]), self.recall_cache
        )
        prefs: dict[str, str] = {}
        if retrieval["pinExplicitPreferences"]:
            prefs.update(memory.active_preferences(self.store, scope))
        else:
            for doc in recalled:
                if doc["kind"] == "preference" and doc.get("key"):
                    prefs[doc["key"]] = str(doc["value"])
        if workflow["schedulingPreferencePass"] and capability == "calendar.find_slots":
            prefs.update(
                {k: v for k, v in memory.active_preferences(self.store, scope).items()
                 if k.startswith("scheduling.")}
            )
        # Read-your-writes: preferences stated in this session apply before index sync.
        prefs.update(memory.session_preferences(self.store, scope))
        notes = [d for d in recalled if d["kind"] != "preference"]
        return prefs, notes, method

    def handle(self, scope: RequestScope, text: str, input_source: str, **kwargs: Any) -> dict[str, Any]:
        run = self._handle(scope, text, input_source, **kwargs)
        telemetry.trace_run(run)  # Redacted, allowlisted fields only; no-op without a key.
        return run

    def _handle(
        self,
        scope: RequestScope,
        text: str,
        input_source: str,
        compiled: dict[str, Any] | None = None,
        voice: dict[str, Any] | None = None,
        version: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        version = version or self.version_for(scope)  # Pinned for the life of this run.
        config = version["config"]
        run = self.store.insert_run(
            scope,
            {
                "inputSource": input_source,
                "identitySource": scope.identity_source,
                "voice": voice,
                "transcript": text,
                "state": "compiling",
                "harnessVersionId": version["_id"],
                "harnessLabel": version.get("label"),
                "startedAt": self.clock(),
            },
        )
        if compiled is None and memory.is_memory_command(text):
            try:
                result = memory.handle_command(self.store, scope, run["_id"], text)
            except COMPILE_ERRORS as exc:
                result = {"capability": "rejected_input", "message": str(exc)}
            self.store.update_run(
                scope,
                run["_id"],
                {"state": "completed", "capability": result["capability"], "result": result,
                 "completedAt": self.clock()},
            )
            return self.store.get_run(scope, run["_id"])
        if compiled is None:
            try:
                compiled = self.compiler.compile(text)
            except COMPILE_ERRORS as exc:
                self.store.update_run(
                    scope,
                    run["_id"],
                    {"state": "failed", "failureCodes": [type(exc).__name__],
                     "completedAt": self.clock()},
                )
                return self.store.get_run(scope, run["_id"])
        capability = tools.route(compiled)
        prefs, notes, recall_method = self.select_context(
            scope, compiled["normalizedCommand"], capability, config
        )
        tool_config = {**TOOL_CONSTANTS, "applyPreferences": True}
        result: dict[str, Any]
        action_ids: list[str] = []
        if capability == "calendar.find_slots":
            result = tools.find_slots(
                self.store, scope, compiled["normalizedCommand"], tool_config, prefs, self.clock()
            )
        elif capability == "mail.prepare":
            result = tools.prepare_mail(self.store, scope, compiled, tool_config, prefs)
            if result["status"] == "prepared":
                action = actions.create_mail_action(self.store, scope, run["_id"], result)
                action_ids.append(action["_id"])
                result["actionId"] = action["_id"]
                result["actionType"] = action["actionType"]
                result["payloadHash"] = action["payloadHash"]
        elif capability == "browser.research":
            private = re.search(r"gmail|mail\.google|calendar\.google|drive\.google|docs\.google", compiled["normalizedCommand"], re.I)
            operator = os.getenv("MARCH_OPERATOR_EMPLOYEE", "emp_asha")
            if private and scope.employee_id != operator:
                result = {"capability": capability, "status": "blocked",
                          "message": "Signed-in accounts (Gmail etc.) are available only to the desk operator. "
                                     "I can open public websites for you."}
            elif browser.enabled(scope):
                task = dict(compiled["intent"])
                urls = tools.browser_targets(compiled["normalizedCommand"])
                if urls:  # Bare domains become explicit URLs the planner may open.
                    task["goal"] = (task["goal"] + " " + " ".join(urls))[:1000]
                if task["intent_type"] not in {"research", "navigate"}:
                    task["intent_type"] = "navigate"  # Read-only office browsing.
                task["needs_clarification"], task["clarifying_question"] = False, None
                task["confidence"] = max(task["confidence"], 0.8)
                browser.start(self.store, scope, run["_id"], task)
                self.store.update_run(
                    scope, run["_id"],
                    {"state": "browsing", "november": compiled, "capability": capability,
                     "result": {"capability": capability, "status": "running",
                                "message": "Researching public pages in the shared desk browser…"}},
                )
                return self.store.get_run(scope, run["_id"])
            else:
                result = {"capability": capability, "status": "disabled",
                          "message": "Browser tasks are disabled in evaluation mode (no live side effects)."}
        elif capability in {"clarify", "cancelled"}:
            result = {"capability": capability, "message": compiled["decision"]["message"]}
        else:
            result = {
                "capability": "unsupported",
                "message": "I can find calendar slots or prepare emails in this demo.",
            }
        if notes:
            result["relatedNotes"] = [{"id": n["_id"], "text": n["text"]} for n in notes]
        self.store.update_run(
            scope,
            run["_id"],
            {
                "state": "completed",
                "november": compiled,
                "capability": capability,
                "result": result,
                "pendingActionIds": action_ids,
                "preferencesUsed": sorted(prefs),
                "selectedMemoryIds": [n["_id"] for n in notes],
                "recallMethod": recall_method,
                "completedAt": self.clock(),
            },
        )
        return self.store.get_run(scope, run["_id"])
