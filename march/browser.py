"""Office browser research via NovemberAI's existing Aside BrowserAdapter (reused as-is).

Read-only office mode: search, open and read public pages. Every click/fill review is refused,
so no website interaction happens. One shared local Aside browser, no employee logins: Aside's
per-employee profile isolation is unverified (doc 06 gate), so private sites stay out of scope.
Results land only in the requesting employee's run."""

import asyncio
import os
import threading
from typing import Any

from march.db import Store, now
from march.scope import RequestScope

BROWSER_LOCK = threading.Lock()  # One shared desk browser; tasks are serialized.
CANCELS: dict[str, threading.Event] = {}
READ_ONLY_REFUSAL = (
    "Office browser is read-only: website interactions (clicks, form fills, sign-ins) are "
    "disabled. Nothing was submitted."
)


def enabled(scope: RequestScope) -> bool:
    return scope.mode == "demo" and os.getenv("MARCH_BROWSER", "1") == "1"


def start(store: Store, scope: RequestScope, run_id: str, intent: dict[str, Any]) -> None:
    cancelled = threading.Event()
    CANCELS[run_id] = cancelled
    threading.Thread(
        target=_work, args=(store, scope, run_id, intent, cancelled), daemon=True,
        name="march-browser",
    ).start()


def cancel(run_id: str) -> bool:
    event = CANCELS.get(run_id)
    if event:
        event.set()
    return event is not None


def _work(
    store: Store, scope: RequestScope, run_id: str, intent: dict[str, Any], cancelled: threading.Event
) -> None:
    from november.aside.adapter import ToolCancelled, ToolFailure
    from november.aside.browser import BrowserAdapter, LocalBrowserPlanner

    steps: list[str] = []

    def progress(message: str) -> None:
        steps.append(message[:200])
        store.update_run(scope, run_id, {"browserProgress": steps[-12:]})

    async def review(details: dict[str, str]) -> None:
        store.update_run(scope, run_id, {"browserRefusedInteraction": {
            k: str(details.get(k, ""))[:200] for k in ("label", "target", "url")}})
        raise ToolFailure(READ_ONLY_REFUSAL)

    if not BROWSER_LOCK.acquire(timeout=1):
        progress("Waiting for the shared desk browser…")
        BROWSER_LOCK.acquire()
    try:
        store.update_run(scope, run_id, {"state": "browsing"})
        adapter = BrowserAdapter(
            os.getenv("NOVEMBER_ASIDE_COMMAND", "aside"),
            planner=LocalBrowserPlanner(
                os.getenv("NOVEMBER_BROWSER_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
            ),
        )
        result = asyncio.run(adapter.execute(intent, cancelled, progress, review))
        store.update_run(scope, run_id, {
            "state": "completed",
            "result": {
                "capability": "browser.research",
                "status": "blocked" if result.blocked else "done",
                "message": result.message,
                "sources": result.sources[:10],
                "label": "Read-only public web research in the shared desk browser (Aside, local).",
            },
            "completedAt": now(),
        })
    except ToolCancelled:
        store.update_run(scope, run_id, {"state": "cancelled", "result": {
            "capability": "browser.research", "status": "cancelled",
            "message": "Cancelled. Check the browser tab; nothing was submitted."}, "completedAt": now()})
    except ToolFailure as exc:
        store.update_run(scope, run_id, {"state": "completed", "result": {
            "capability": "browser.research", "status": "stopped", "message": str(exc)[:400]},
            "completedAt": now()})
    except Exception as exc:  # Unknown failures are reported, never relabeled as success.
        store.update_run(scope, run_id, {"state": "failed", "failureCodes": [type(exc).__name__],
                                          "result": {"capability": "browser.research",
                                                     "status": "error",
                                                     "message": "The browser task failed."},
                                          "completedAt": now()})
    finally:
        BROWSER_LOCK.release()
        CANCELS.pop(run_id, None)
