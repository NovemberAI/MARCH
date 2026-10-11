"""Thin adapter over NovemberAI's existing compiler and policy. No parsing logic lives here."""

import os
from dataclasses import asdict
from typing import Any, Protocol

from november.asr.editing import EditingUnavailable, LocalTranscriptEditor
from november.input import InputProblem
from november.intent.compiler import Compiler
from november.intent.model import ModelUnavailable, OfflineModel, OllamaModel
from november.intent.validation import InvalidIntent

COMPILE_ERRORS = (InputProblem, EditingUnavailable, ModelUnavailable, InvalidIntent)


class IntentSource(Protocol):
    label: str

    def compile(self, text: str) -> dict[str, Any]: ...


class NovemberCompiler:
    """Calls november.intent.compiler.Compiler exactly as November's own CLI builds it."""

    def __init__(self, mode: str = "live") -> None:
        if mode == "offline":
            self.compiler = Compiler(OfflineModel())
            self.label = "november_offline_diagnostic_grammar"
        else:
            self.compiler = Compiler(
                OllamaModel(
                    os.getenv("NOVEMBER_MODEL", "qwen2.5:3b"),
                    float(os.getenv("NOVEMBER_MODEL_TIMEOUT", "30")),
                ),
                editor=LocalTranscriptEditor(
                    os.getenv("NOVEMBER_EDITOR_MODEL", "qwen3.5:9b"),
                    timeout=float(os.getenv("NOVEMBER_EDITOR_TIMEOUT", "60")),
                ),
            )
            self.label = "november_live_local_models"

    def compile(self, text: str) -> dict[str, Any]:
        result = self.compiler.compile(text)
        return {
            "normalizedCommand": result.normalized_command,
            "intent": dict(result.structured_intent),
            "decision": asdict(result.decision),
            "source": result.source,
            "latencyMs": result.latency_ms,
            "compiler": self.label,
        }
