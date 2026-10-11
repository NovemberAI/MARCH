from datetime import timedelta

import pytest

from march import actions
from march.scope import RequestScope, ScopeError
from tests.conftest import FIXED_NOW

SEND = "email Priya about the launch"
DRAFT = "draft an email to Priya about the launch, but do not send it"


def test_slots_use_only_own_calendar(orch, asha):
    run = orch.handle(asha, "find a 30 minute slot with Ben tomorrow", "november_text")
    result = run["result"]
    assert result["capability"] == "calendar.find_slots"
    assert result["timeZone"] == "America/Los_Angeles"
    # Asha is busy 09:00-10:00 tomorrow; Ben's 09:30-11:00 block must not affect her slots.
    assert result["slots"][0] == {"start": "10:00", "end": "10:30"}


def test_same_contact_name_resolves_per_employee(orch, asha, casey):
    a = orch.handle(asha, SEND, "november_text")["result"]["payload"]["to"]
    c = orch.handle(casey, SEND, "november_text")["result"]["payload"]["to"]
    assert a == ["priya.asha-team@demo-office.example"]
    assert c == ["priya.casey-vendor@demo-partner.example"]


def test_cross_employee_reads_denied(orch, store, asha, ben):
    run = orch.handle(asha, SEND, "november_text")
    action_id = run["pendingActionIds"][0]
    with pytest.raises(ScopeError):
        store.get_run(ben, run["_id"])
    with pytest.raises(ScopeError):
        store.get_action(ben, action_id)
    assert store.recent_runs(ben) == []
    assert store.list_actions(ben, ["pending"]) == []


def test_scope_rejects_unknown_employee_and_live_mode():
    with pytest.raises(ScopeError):
        RequestScope("demo", "demo_office", "emp_mallory", "s", "manual_fixture")
    with pytest.raises(ScopeError):
        RequestScope("live", "demo_office", "emp_asha", "s", "manual_fixture")


def test_insert_ignores_forged_scope_fields(store, asha):
    run = store.insert_run(asha, {"employeeId": "emp_ben", "orgId": "evil", "transcript": "x"})
    assert run["employeeId"] == "emp_asha" and run["orgId"] == "demo_office"


def test_owner_approval_executes_once(orch, store, asha):
    run = orch.handle(asha, SEND, "november_text")
    action = store.get_action(asha, run["pendingActionIds"][0])
    done = actions.approve(store, asha, action["_id"], action["payloadHash"])
    assert done["state"] == "simulated_sent"
    assert len(store.simulated_sends(asha)) == 1
    with pytest.raises(actions.ApprovalRejected) as exc:
        actions.approve(store, asha, action["_id"], action["payloadHash"])
    assert exc.value.code == "state_simulated_sent"
    assert len(store.simulated_sends(asha)) == 1


def test_other_employee_cannot_approve(orch, store, asha, ben):
    run = orch.handle(asha, SEND, "november_text")
    action = store.get_action(asha, run["pendingActionIds"][0])
    with pytest.raises(ScopeError):
        actions.approve(store, ben, action["_id"], action["payloadHash"])
    assert store.get_action(asha, action["_id"])["state"] == "pending"
    assert store.simulated_sends(ben) == [] and store.simulated_sends(asha) == []


def test_changed_payload_invalidates_approval(orch, store, asha):
    run = orch.handle(asha, SEND, "november_text")
    action = store.get_action(asha, run["pendingActionIds"][0])
    old_hash = action["payloadHash"]
    edited = actions.edit_payload(store, asha, action["_id"], {"to": ["attacker@evil.example"]})
    assert edited["payloadHash"] != old_hash
    with pytest.raises(actions.ApprovalRejected) as exc:
        actions.approve(store, asha, action["_id"], old_hash)
    assert exc.value.code == "payload_changed"
    assert store.simulated_sends(asha) == []


def test_expired_approval_rejected(orch, store, asha):
    run = orch.handle(asha, SEND, "november_text")
    action = store.get_action(asha, run["pendingActionIds"][0])
    later = action["expiresAt"] + timedelta(seconds=1)
    with pytest.raises(actions.ApprovalRejected) as exc:
        actions.approve(store, asha, action["_id"], action["payloadHash"], at=later)
    assert exc.value.code == "expired"


def test_draft_but_do_not_send_is_never_dispatchable(orch, store, asha):
    run = orch.handle(asha, DRAFT, "november_text")
    action = store.get_action(asha, run["pendingActionIds"][0])
    assert action["actionType"] == "mail.draft" and action["dispatchable"] is False
    assert "send" in action["prohibitedActions"]
    with pytest.raises(actions.ApprovalRejected) as exc:
        actions.approve(store, asha, action["_id"], action["payloadHash"])
    assert exc.value.code == "draft_only_not_sendable"
    assert store.simulated_sends(asha) == []


def test_model_claiming_approval_has_no_effect(orch, store, compiler, asha):
    out = compiler.outputs[SEND]
    out["intent"]["requires_approval"] = False
    out["decision"]["message"] = "Approved and sent!"
    run = orch.handle(asha, SEND, "november_text")
    action = store.get_action(asha, run["pendingActionIds"][0])
    assert action["state"] == "pending" and action["approval"] is None
    assert store.simulated_sends(asha) == []


def test_clock_is_fixed_for_determinism():
    assert FIXED_NOW.isoformat().startswith("2026-10-11")


def test_research_routes_to_browser_but_eval_mode_never_browses(store, compiler):
    from march.orchestrator import Orchestrator
    from tests.conftest import FIXED_NOW, november_output

    compiler.add(november_output("look up the opening hours of the city library", "research", ["city library"]))
    ev = store.open_session("eval", "demo_office", "emp_asha", "manual_fixture")
    store.db.employees.insert_one({"mode": "eval", "orgId": "demo_office", "employeeId": "emp_asha",
                                   "displayName": "Asha", "timeZone": "America/Los_Angeles",
                                   "fixtureEmail": "asha@demo-office.example"})
    run = Orchestrator(store, compiler, clock=lambda: FIXED_NOW).handle(
        ev, "look up the opening hours of the city library", "eval_fixture")
    assert run["capability"] == "browser.research"
    assert run["result"]["status"] == "disabled"


def test_email_command_never_routes_to_browser(orch, compiler, asha):
    from tests.conftest import november_output

    compiler.add(november_output("email Asha about the quarterly numbers", "research", ["Asha"]))
    run = orch.handle(asha, "email Asha about the quarterly numbers", "november_text")
    assert run["capability"] == "mail.prepare"


def test_email_followups_fuzzy_names_and_real_addresses(orch, compiler, store, asha):
    from tests.conftest import november_output

    compiler.add(november_output("Email Priya about the launch plan.", "research", ["Priya"]))
    run = orch.handle(asha, "Email Priya about the launch plan.", "november_voice")
    assert run["capability"] == "mail.prepare" and run["result"]["status"] == "prepared"

    compiler.add(november_output("draft an email to bend about the budget but do not send it.", "draft", ["Bend", "budget"], prohibited=["send"]))
    run = orch.handle(asha, "draft an email to bend about the budget but do not send it.", "november_voice")
    assert run["result"]["payload"]["to"] == ["ben@demo-office.example"] and run["result"]["heardAs"] == "Bend"
    assert store.get_action(asha, run["pendingActionIds"][0])["dispatchable"] is False

    text = "The email should be about the budget. So just say what's the status of the budget."
    compiler.add(november_output(text, "research", []))
    run = orch.handle(asha, text, "november_voice")
    assert run["result"]["payload"]["to"] == ["ben@demo-office.example"]
    assert "What's the status of the budget?" in run["result"]["payload"]["body"]

    text = "Now I need you to send it to Ben12345678 at gmail.com"
    compiler.add(november_output(text, "execute", ["Ben12345678 at gmail.com"]))
    run = orch.handle(asha, text, "november_voice")
    assert run["result"]["status"] == "clarify" and "real addresses" in run["result"]["message"]
    assert not run["pendingActionIds"]
