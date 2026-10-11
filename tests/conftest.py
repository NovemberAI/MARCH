from datetime import UTC, datetime
from typing import Any

import mongomock
import pytest

from march.db import Store
from march.fixtures import seed
from march.orchestrator import Orchestrator

ORG = "demo_office"
FIXED_NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)


def november_output(command: str, intent_type: str, entities: list[str], prohibited=(), constraints=()):
    """Shape of november_bridge.NovemberCompiler.compile(); values recorded from live runs."""
    return {
        "normalizedCommand": command,
        "intent": {
            "intent_type": intent_type,
            "goal": command,
            "entities": list(entities),
            "constraints": list(constraints),
            "prohibited_actions": list(prohibited),
            "requires_approval": False,
            "confidence": 1.0,
            "needs_clarification": False,
            "clarifying_question": None,
        },
        "decision": {"status": "ready", "message": "Your proposal is ready. Nothing has been carried out."},
        "source": "model",
        "latencyMs": 0.0,
        "compiler": "recorded_november_live_output",
    }


class RecordedCompiler:
    label = "recorded_november_live_output"

    def __init__(self) -> None:
        self.outputs: dict[str, dict[str, Any]] = {}

    def add(self, output: dict[str, Any]) -> None:
        self.outputs[output["normalizedCommand"]] = output

    def compile(self, text: str) -> dict[str, Any]:
        return self.outputs[text]


@pytest.fixture
def db():
    database = mongomock.MongoClient(tz_aware=True)["march_test"]
    seed(database, "demo", ORG)
    return database


@pytest.fixture
def store(db):
    return Store(db)


@pytest.fixture
def compiler():
    c = RecordedCompiler()
    c.add(november_output("find a 30 minute slot with Ben tomorrow", "research", ["Ben", "30 minute slot"], constraints=["tomorrow"]))
    c.add(november_output("draft an email to Priya about the launch, but do not send it", "draft", ["Priya", "launch"], prohibited=["send"]))
    c.add(november_output("email Priya about the launch", "draft", ["Priya", "launch"]))
    return c


@pytest.fixture
def orch(store, compiler):
    return Orchestrator(store, compiler, clock=lambda: FIXED_NOW)


@pytest.fixture
def asha(store):
    return store.open_session("demo", ORG, "emp_asha", "manual_fixture")


@pytest.fixture
def ben(store):
    return store.open_session("demo", ORG, "emp_ben", "manual_fixture")


@pytest.fixture
def casey(store):
    return store.open_session("demo", ORG, "emp_casey", "manual_fixture")
