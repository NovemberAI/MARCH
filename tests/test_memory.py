from march import memory
from tests.conftest import november_output

SLOT = "find a 30 minute slot with Ben tomorrow"


def test_explicit_preference_used_on_very_next_request(orch, asha):
    before = orch.handle(asha, SLOT, "november_text")["result"]["slots"][0]
    assert before == {"start": "10:00", "end": "10:30"}
    noted = orch.handle(asha, "remember that I prefer afternoon meetings", "november_text")
    assert noted["capability"] == "memory.remember"
    after = orch.handle(asha, SLOT, "november_text")["result"]
    assert after["slots"][0] == {"start": "14:00", "end": "14:30"}  # 13:00-14:00 is busy.
    assert "scheduling.preferred_period=afternoon" in after["appliedPreferences"]


def test_preferences_are_private(orch, asha, ben):
    orch.handle(asha, "I prefer afternoon meetings", "november_text")
    assert memory.active_preferences(orch.store, ben) == {}
    assert memory.list_active(orch.store, ben) == []
    assert memory.recall(orch.store, ben, "afternoon meetings", 4)[0] == []


def test_correction_supersedes_and_keeps_history(orch, store, asha):
    orch.handle(asha, "I prefer afternoon meetings", "november_text")
    orch.handle(asha, "actually I prefer morning meetings", "november_text")
    assert memory.active_preferences(store, asha) == {"scheduling.preferred_period": "morning"}
    history = list(store.db.memories.find({**asha.filter(), "key": "scheduling.preferred_period"}))
    assert sorted(m["status"] for m in history) == ["active", "superseded"]
    new = next(m for m in history if m["status"] == "active")
    assert new["supersedesId"] == next(m for m in history if m["status"] == "superseded")["_id"]


def test_forget_excludes_immediately_and_purges_text(orch, store, asha):
    orch.handle(asha, "remember that the Q4 offsite is in Lisbon", "november_text")
    assert memory.recall(store, asha, "where is the offsite", 4)[0]
    out = orch.handle(asha, "forget the offsite", "november_text")["result"]
    assert out["forgotten"] == 1
    assert memory.recall(store, asha, "where is the offsite", 4)[0] == []
    gone = store.db.memories.find_one({**asha.filter(), "status": "deleted"})
    assert "Lisbon" not in gone["text"]
    assert store.db.memory_tombstones.count_documents(asha.filter()) == 1


def test_what_do_you_remember_is_scoped(orch, asha, casey):
    orch.handle(asha, "keep my emails short", "november_text")
    mine = orch.handle(asha, "what do you remember about me", "november_text")["result"]["items"]
    theirs = orch.handle(casey, "what do you remember about me", "november_text")["result"]["items"]
    assert [i["text"] for i in mine] == ["Prefers brief emails."] and theirs == []


def test_brief_preference_changes_email(orch, store, asha):
    long = orch.handle(asha, "email Priya about the launch", "november_text")["result"]["payload"]["body"]
    orch.handle(asha, "keep my emails short", "november_text")
    short = orch.handle(asha, "email Priya about the launch", "november_text")["result"]["payload"]["body"]
    assert len(short) < len(long)


def test_credentials_rejected_before_memory(orch, store, asha):
    run = orch.handle(asha, "remember that my password is hunter2", "november_text")
    assert run["capability"] == "rejected_input"
    assert store.db.memories.count_documents(asha.filter()) == 0
