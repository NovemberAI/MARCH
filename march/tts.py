"""ElevenLabs text-to-speech for short, generic desk acknowledgments.

Privacy gate: only text rendered from the fixed template set below can ever be
sent to ElevenLabs. Email bodies, subjects, recipients, slot times, memory text
and web results are never spoken. First names are limited to the fictional
fixture employees. The API key and spoken text are never logged.
"""

from __future__ import annotations

import os
import threading

import httpx

import march.config  # noqa: F401  (loads .env)

API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs premade voice "Rachel"
MODEL_ID = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
TIMEOUT_S = 10.0

ALLOWED_NAMES = frozenset({"Asha", "Ben", "Casey"})

# (template with a name, template without a name)
TEMPLATES: dict[str, tuple[str, str]] = {
    "slots_ready": ("{name}, your slots are on the screen.", "Your slots are on the screen."),
    "draft_ready": ("{name}, your draft is ready to review.", "Your draft is ready to review."),
    "approval_needed": (
        "{name}, this needs your approval on the screen.",
        "This needs your approval on the screen.",
    ),
    "research_done": ("{name}, your results are on the screen.", "Your results are on the screen."),
    "noted": ("Got it, {name}. I've noted that.", "Got it. I've noted that."),
    "unknown_speaker": (
        "Sorry, I don't recognize your voice. Please pick your profile.",
        "Sorry, I don't recognize your voice. Please pick your profile.",
    ),
    "cancelled": ("Okay, {name}. Cancelled.", "Okay. Cancelled."),
    "error": ("Sorry, {name}, something went wrong.", "Sorry, something went wrong."),
}


class NotAllowedText(ValueError):
    """Raised when text outside the acknowledgment template set is offered to TTS."""


def _safe_name(first_name: str | None) -> str | None:
    return first_name if first_name in ALLOWED_NAMES else None


def acknowledgment(kind: str, first_name: str | None) -> str:
    """Render a fixed acknowledgment. Unknown kinds raise; unknown names are omitted."""
    if kind not in TEMPLATES:
        raise NotAllowedText("unknown acknowledgment kind")
    with_name, without_name = TEMPLATES[kind]
    name = _safe_name(first_name)
    if kind == "unknown_speaker" or name is None:
        return without_name
    return with_name.format(name=name)


# Every string that may ever leave the process. Finite and computed up front.
ALLOWED_TEXTS: frozenset[str] = frozenset(
    acknowledgment(kind, name)
    for kind in TEMPLATES
    for name in (None, *sorted(ALLOWED_NAMES))
)

_cache: dict[str, bytes] = {}
_lock = threading.Lock()


def configured() -> bool:
    return bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())


def speak(text: str) -> bytes | None:
    """Return MP3 bytes for an allowlisted acknowledgment, or None if TTS is unavailable.

    Raises NotAllowedText for anything not produced by `acknowledgment()`.
    """
    if text not in ALLOWED_TEXTS:
        raise NotAllowedText("text is not an approved acknowledgment")
    with _lock:
        cached = _cache.get(text)
    if cached is not None:
        return cached
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return None
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
    try:
        response = httpx.post(
            f"{API_BASE}/{voice_id}",
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
            json={"text": text, "model_id": MODEL_ID},
            timeout=TIMEOUT_S,
        )
    except httpx.HTTPError as exc:
        print(f"tts: request failed ({type(exc).__name__})")
        return None
    if response.status_code != 200 or not response.content:
        print(f"tts: elevenlabs returned HTTP {response.status_code}")
        return None
    audio = response.content
    with _lock:
        _cache[text] = audio
    return audio


def speak_ack(kind: str, first_name: str | None) -> bytes | None:
    """Convenience: render and speak in one step."""
    return speak(acknowledgment(kind, first_name))
