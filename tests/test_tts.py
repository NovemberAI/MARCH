import httpx
import pytest

from march import tts


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    tts._cache.clear()
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    yield
    tts._cache.clear()


def test_template_rendering():
    assert tts.acknowledgment("slots_ready", "Ben") == "Ben, your slots are on the screen."
    assert tts.acknowledgment("slots_ready", None) == "Your slots are on the screen."
    for kind in tts.TEMPLATES:
        assert tts.acknowledgment(kind, "Asha") in tts.ALLOWED_TEXTS
    with pytest.raises(tts.NotAllowedText):
        tts.acknowledgment("read_email_body", "Ben")


def test_name_allowlist():
    assert "Mallory" not in tts.acknowledgment("draft_ready", "Mallory")
    assert tts.acknowledgment("draft_ready", "Mallory") == tts.acknowledgment("draft_ready", None)
    assert tts.acknowledgment("draft_ready", "ben") == "Your draft is ready to review."
    assert "Casey" in tts.acknowledgment("draft_ready", "Casey")
    # Unknown speaker never names anyone.
    assert "Ben" not in tts.acknowledgment("unknown_speaker", "Ben")


@pytest.mark.parametrize("text", [
    "Your meeting with Dana is at 3pm Tuesday.",
    "Subject: Q3 budget",
    "Ben, your slots are on the screen. Also, the password is hunter2.",
    "",
])
def test_refuses_arbitrary_text(monkeypatch, text):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    called = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: called.append(1))
    with pytest.raises(tts.NotAllowedText):
        tts.speak(text)
    assert not called


def test_no_network_without_key(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call without key")

    monkeypatch.setattr(httpx, "post", boom)
    assert tts.speak(tts.acknowledgment("noted", "Ben")) is None
    assert not tts.configured()


def test_mocked_call_sends_only_template_text_and_caches(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice123")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, content=b"ID3fake-mp3")

    monkeypatch.setattr(httpx, "post", fake_post)
    text = tts.acknowledgment("slots_ready", "Ben")
    assert tts.speak(text) == b"ID3fake-mp3"
    assert tts.speak(text) == b"ID3fake-mp3"  # cached
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://api.elevenlabs.io/v1/text-to-speech/voice123"
    assert kwargs["json"] == {"text": "Ben, your slots are on the screen.", "model_id": tts.MODEL_ID}
    assert kwargs["headers"]["xi-api-key"] == "test-key"
    assert kwargs["timeout"] == 10.0


def test_http_error_returns_none(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(401, content=b"no"))
    assert tts.speak_ack("error", None) is None
    assert tts._cache == {}
