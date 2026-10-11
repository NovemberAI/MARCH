"""Local MARCH web/API server (stdlib, matching November's own server style)."""

import json
import os
import re
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from march import actions, memory
from march.config import FIXTURE_EMPLOYEES, Settings, settings
from march.db import Store, connect
from march.fixtures import seed
from march.november_bridge import NovemberCompiler
from march.orchestrator import Orchestrator
from march.scope import RequestScope, ScopeError

UI = Path(__file__).parent / "ui"
APP_VERSION = "0.1.0"
COOKIE = "march_session"


def _json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


class App:
    def __init__(self, cfg: Settings, store: Store, orch: Orchestrator, persistence: str) -> None:
        self.cfg, self.store, self.orch, self.persistence = cfg, store, orch, persistence
        self.cycle: dict[str, Any] = {"state": "idle", "log": []}
        self.voice: Any = None
        self.desk: Any = None
        self.voice_error = ""

    def health(self) -> dict[str, Any]:
        atlas = False
        if self.persistence == "atlas":
            try:
                self.store.db.command("ping")
                atlas = True
            except Exception:
                atlas = False
        return {
            "status": "ok",
            "appVersion": APP_VERSION,
            "mode": self.cfg.mode,
            "persistence": self.persistence,
            "atlasReady": atlas,
            "compiler": self.orch.compiler.label,
            "voice": self.voice is not None,
            "voiceError": self.voice_error,
            "voiceProfiles": len(self.desk.profiles.enrolled()) if self.desk else 0,
            "vectorIndex": self._vector_ready(),
        }

    def _vector_ready(self) -> bool:
        if self.persistence != "atlas":
            return False
        try:
            return any(
                i.get("queryable") for i in self.store.db.memories.list_search_indexes(memory.INDEX)
            )
        except Exception:
            return False

    def harness_view(self, scope: RequestScope) -> dict[str, Any]:
        from march.harness import Harness

        h = Harness(self.store.db, scope.mode, scope.org_id)
        active = h.active(scope.employee_id)
        versions = list(self.store.db.harness_versions.find(
            {"mode": scope.mode, "orgId": scope.org_id, "employeeId": scope.employee_id}
        ).sort("createdAt", 1))
        last = None
        if self.cycle.get("evaluationId") and self.cycle.get("employeeId") == scope.employee_id:
            from march.db import connect

            ev = connect(self.cfg, "eval").evaluations.find_one({"_id": self.cycle["evaluationId"]})
            if ev:
                last = {k: ev.get(k) for k in ("_id", "suiteVersion", "gateDecision", "failureCodes",
                                               "proposal", "aggregate", "heldOutTest", "repetitions",
                                               "tokenUsage")}
                last["baselineRates"] = (ev.get("baseline") or {}).get("rates")
                last["candidateRates"] = (ev.get("candidate") or {}).get("rates")
                last["baselineFailures"] = [
                    {"id": r["id"], "failures": r["failures"]}
                    for r in ((ev.get("baseline") or {}).get("first") or {}).get("results", []) if not r["pass"]]
                last["candidateFailures"] = [
                    {"id": r["id"], "failures": r["failures"]}
                    for r in ((ev.get("candidate") or {}).get("first") or {}).get("results", []) if not r["pass"]]
        return {
            "active": {"id": active["_id"], "label": active.get("label"), "config": active["config"]},
            "versions": [{"id": v["_id"], "label": v.get("label"), "status": v.get("lifecycleStatus"),
                          "patch": v.get("patch"), "rationale": v.get("rationale"),
                          "rejectionReasons": v.get("rejectionReasons")} for v in versions],
            "cycle": {k: self.cycle.get(k) for k in ("state", "log", "employeeId")},
            "lastEvaluation": last,
        }

    def start_cycle(self, scope: RequestScope) -> None:
        import threading

        from march.db import connect
        from march.evaluation import EVAL_CLOCK
        from march.improve import run_cycle

        if self.cycle["state"] == "running":
            raise ValueError("busy")
        self.cycle = {"state": "running", "log": [], "employeeId": scope.employee_id}

        class NoCompiler:
            label = "cached_november_outputs_only"

            def compile(self, text: str) -> dict[str, Any]:
                raise RuntimeError("evaluation uses cached November outputs only")

        def work() -> None:
            try:
                ev = Store(connect(self.cfg, "eval"))
                seed(ev.db, "eval", self.cfg.org_id)
                orch = Orchestrator(ev, NoCompiler(), clock=lambda: EVAL_CLOCK)
                record = run_cycle(self.store, ev, orch, self.cfg.org_id, scope.employee_id,
                                   progress=lambda m: self.cycle["log"].append(m))
                self.cycle.update(state="done", evaluationId=record["_id"])
            except Exception as exc:
                self.cycle.update(state="error", error=type(exc).__name__)
                self.cycle["log"].append(f"Cycle failed: {type(exc).__name__}")

        threading.Thread(target=work, daemon=True, name="march-improve").start()

    def view(self, scope: RequestScope) -> dict[str, Any]:
        employee = self.store.employee(scope)
        return {
            "employee": {
                "id": scope.employee_id,
                "displayName": employee["displayName"],
                "timeZone": employee["timeZone"],
                "identitySource": scope.identity_source,
            },
            "runs": [_public_run(r) for r in self.store.recent_runs(scope, 8)],
            "actions": [
                _public_action(a)
                for a in self.store.list_actions(
                    scope, ["pending", "draft", "simulated_sent", "rejected", "expired"]
                )[:8]
            ],
        }


def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    keys = ["_id", "inputSource", "identitySource", "transcript", "state", "capability",
            "result", "harnessVersionId", "pendingActionIds", "preferencesUsed", "recallMethod",
            "failureCodes", "createdAt", "voice", "browserProgress", "browserRefusedInteraction",
            "harnessLabel"]
    out = {k: run.get(k) for k in keys}
    november = run.get("november") or {}
    out["november"] = {
        k: november.get(k) for k in ["normalizedCommand", "intent", "decision", "compiler", "latencyMs"]
    }
    return out


def _public_action(action: dict[str, Any]) -> dict[str, Any]:
    keys = ["_id", "actionType", "dispatchable", "normalizedPayload", "payloadHash", "state",
            "prohibitedActions", "constraints", "expiresAt", "approval", "providerResult"]
    return {k: action.get(k) for k in keys}


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "MARCH"

        def log_message(self, fmt: str, *args: Any) -> None:  # no bodies or cookies in logs
            print(f"{self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}")

        def _send(self, status: int, body: Any, cookie: str | None = None) -> None:
            data = json.dumps(body, default=_json).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            if cookie is not None:
                self.send_header(
                    "Set-Cookie", f"{COOKIE}={cookie}; HttpOnly; SameSite=Strict; Path=/"
                )
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 65536:
                raise ValueError("too large")
            raw = self.rfile.read(length) if length else b"{}"
            value = json.loads(raw or b"{}")
            if not isinstance(value, dict):
                raise ValueError("object expected")
            return value

        def _scope(self) -> RequestScope:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            if COOKIE not in cookie:
                raise ScopeError("no session")
            return app.store.resume_session(cookie[COOKIE].value)

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/health":
                return self._send(200, app.health())
            if path in {"/", "/index.html"}:
                data = (UI / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(data)
                return None
            if path == "/audio-worklet.js":
                # November's own capture worklet, served unmodified from the installed package.
                from importlib.resources import files

                data = files("november.ui").joinpath("audio-worklet.js").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript")
                self.end_headers()
                self.wfile.write(data)
                return None
            if path == "/api/voice/status":
                if not app.voice:
                    return self._send(200, {"available": False, "error": app.voice_error})
                return self._send(200, {**app.voice.snapshot(), "desk": app.desk.status()})
            run_match = re.fullmatch(r"/api/runs/([\w-]+)", path)
            if run_match:
                try:
                    return self._send(200, _public_run(app.store.get_run(self._scope(), run_match[1])))
                except ScopeError:
                    return self._send(404, {"error": "not_found_or_not_permitted"})
            if path == "/api/harness":
                try:
                    return self._send(200, app.harness_view(self._scope()))
                except ScopeError:
                    return self._send(401, {"error": "no_session"})
            if path == "/api/me":
                try:
                    return self._send(200, app.view(self._scope()))
                except ScopeError:
                    return self._send(401, {"error": "no_session"})
            return self._send(404, {"error": "not_found"})

        def do_POST(self) -> None:
            path = self.path.split("?")[0]
            try:
                if path.startswith(("/api/voice/", "/api/enroll/")):
                    return self._voice(path)
                body = self._body()
                if path == "/api/demo/select-profile":
                    employee_id = body.get("fixtureEmployeeId")
                    if app.cfg.mode != "demo" or employee_id not in FIXTURE_EMPLOYEES:
                        return self._send(400, {"error": "invalid_fixture_identity"})
                    scope = app.store.open_session(
                        "demo", app.cfg.org_id, employee_id, "manual_fixture"
                    )
                    return self._send(200, app.view(scope), cookie=scope.session_id)
                scope = self._scope()
                if path == "/api/runs":
                    text = str(body.get("text", ""))[:600]
                    run = app.orch.handle(scope, text, "november_text")
                    return self._send(200, {"run": _public_run(run), **app.view(scope)})
                if path == "/api/tts":
                    from march import tts

                    kind = str(body.get("kind", ""))
                    if kind not in tts.TEMPLATES:
                        return self._send(400, {"error": "bad_tts_kind"})
                    first = {"emp_asha": "Asha", "emp_ben": "Ben", "emp_casey": "Casey"}.get(scope.employee_id)
                    audio = tts.speak(tts.acknowledgment(kind, first))
                    if audio is None:
                        self.send_response(204)
                        self.end_headers()
                        return None
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(audio)))
                    self.end_headers()
                    self.wfile.write(audio)
                    return None
                if path == "/api/harness/improve":
                    app.start_cycle(scope)
                    return self._send(200, app.harness_view(scope))
                if path == "/api/harness/rollback":
                    from march.harness import Harness

                    ok = Harness(app.store.db, scope.mode, scope.org_id).rollback(
                        scope.employee_id, str(body.get("targetVersionId", "")), "owner rollback")
                    return self._send(200 if ok else 409, app.harness_view(scope))
                fb = re.fullmatch(r"/api/runs/([\w-]+)/feedback", path)
                if fb:
                    app.store.get_run(scope, fb[1])
                    kind = body.get("type")
                    if kind not in {"correction", "explicit_accept", "explicit_reject", "verified_failure"}:
                        return self._send(400, {"error": "bad_feedback_type"})
                    from march.db import new_id, now as _now

                    app.store.db.feedback.insert_one({
                        "_id": new_id(), **scope.filter(), "runId": fb[1], "type": kind,
                        "structuredCorrection": str(body.get("structuredCorrection", ""))[:200],
                        "sourcePrincipalId": scope.employee_id, "createdAt": _now()})
                    return self._send(200, {"ok": True})
                cancel_match = re.fullmatch(r"/api/runs/([\w-]+)/cancel", path)
                if cancel_match:
                    app.store.get_run(scope, cancel_match[1])  # Owner check before cancelling.
                    from march import browser

                    return self._send(200, {"cancelled": browser.cancel(cancel_match[1])})
                match = re.fullmatch(r"/api/actions/([\w-]+)/(approve|reject|edit)", path)
                if match:
                    action_id, verb = match[1], match[2]
                    if verb == "approve":
                        actions.approve(
                            app.store, scope, action_id, str(body.get("displayedPayloadHash", ""))
                        )
                    elif verb == "reject":
                        actions.reject(app.store, scope, action_id)
                    else:
                        changes = {k: body[k] for k in ("to", "subject", "body") if k in body}
                        actions.edit_payload(app.store, scope, action_id, changes)
                    return self._send(200, app.view(scope))
                return self._send(404, {"error": "not_found"})
            except actions.ApprovalRejected as exc:
                return self._send(409, {"error": exc.code})
            except ScopeError:
                return self._send(404, {"error": "not_found_or_not_permitted"})
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"error": "bad_request"})

        def _voice(self, path: str) -> None:
            from november.input import InputProblem

            if not app.voice:
                return self._send(503, {"error": "voice_unavailable"})
            loop, desk = app.voice, app.desk
            try:
                if path == "/api/voice/frame":
                    length = int(self.headers.get("Content-Length") or 0)
                    if not 0 < length <= 4096:
                        raise InputProblem("bad frame")
                    return self._send(
                        200,
                        loop.feed(
                            self.rfile.read(length),
                            self.headers.get("X-Capture-Id", ""),
                            int(self.headers.get("X-Audio-Sequence", "-1")),
                        ),
                    )
                body = self._body()
                if path == "/api/voice/start":
                    return self._send(200, loop.start())
                if path == "/api/voice/stop":
                    return self._send(200, loop.stop())
                if path == "/api/voice/cancel":
                    return self._send(200, loop.cancel())
                if path == "/api/voice/hold/start":
                    return self._send(200, loop.hold_start())
                if path == "/api/voice/finish":
                    return self._send(
                        200,
                        loop.finish(str(body.get("capture_id", "")), int(body.get("wake_count", -1))),
                    )
                if path == "/api/voice/adopt":
                    session_id = desk.adopt(str(body.get("token", "")))
                    if not session_id:
                        return self._send(404, {"error": "expired"})
                    scope = app.store.resume_session(session_id)
                    return self._send(200, app.view(scope), cookie=session_id)
                if path == "/api/voice/revoke":
                    scope = self._scope()  # Only the current owner session may revoke its profile.
                    app.desk.profiles.revoke(scope.employee_id)
                    return self._send(200, desk.status())
                if path == "/api/enroll/start":
                    employee_id = body.get("fixtureEmployeeId")
                    if body.get("consent") is not True or employee_id not in FIXTURE_EMPLOYEES:
                        return self._send(400, {"error": "consent_and_fixture_identity_required"})
                    return self._send(200, desk.start_enrollment(employee_id))
                if path == "/api/enroll/cancel":
                    return self._send(200, desk.cancel_enrollment())
                return self._send(404, {"error": "not_found"})
            except InputProblem as exc:
                return self._send(409, {"error": str(exc)})

    return Handler


def build_app(cfg: Settings | None = None) -> App:
    cfg = cfg or settings()
    if cfg.atlas_configured:
        db = connect(cfg, cfg.mode)
        persistence = "atlas"
    else:
        import mongomock

        db = mongomock.MongoClient(tz_aware=True)[cfg.db_name(cfg.mode)]
        persistence = "in_memory_fallback_NOT_PERSISTED"
    seed(db, cfg.mode, cfg.org_id)
    store = Store(db)
    orch = Orchestrator(store, NovemberCompiler(cfg.compiler))
    app = App(cfg, store, orch, persistence)
    if os.getenv("MARCH_VOICE", "1") == "1":
        try:
            from march.voice import build_voice

            app.voice, app.desk = build_voice(store, orch, cfg.mode, cfg.org_id)
        except Exception as exc:  # Voice is optional; typed input keeps working.
            app.voice_error = type(exc).__name__
    return app


def main() -> None:
    app = build_app()
    server = ThreadingHTTPServer(("127.0.0.1", app.cfg.port), make_handler(app))
    print(f"MARCH ready at http://127.0.0.1:{app.cfg.port} persistence={app.persistence} "
          f"compiler={app.orch.compiler.label}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
