import json

import pytest

from providers.liquid import LiquidMalformedResponse, LiquidNotConfigured, LiquidProvider


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return json.dumps(self.value).encode()


def test_liquid_missing_key_is_visibly_not_configured(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LiquidNotConfigured, match="no fallback"):
        LiquidProvider(api_key="")


def test_liquid_authenticated_structured_response(monkeypatch):
    response = {"choices": [{"message": {"content": json.dumps({"root_cause": "auth"})}}]}
    monkeypatch.setattr("providers.liquid.urlopen", lambda request, timeout: FakeResponse(response))
    provider = LiquidProvider(api_key="openrouter_test", base_url="https://example.invalid/v1")
    assert provider.compile("system", {"events": []}) == {"root_cause": "auth"}
    assert provider.status.state == "CONNECTED"


def test_liquid_malformed_response_is_error(monkeypatch):
    response = {"choices": [{"message": {"content": "not-json"}}]}
    monkeypatch.setattr("providers.liquid.urlopen", lambda request, timeout: FakeResponse(response))
    provider = LiquidProvider(api_key="openrouter_test")
    with pytest.raises(LiquidMalformedResponse):
        provider.compile("system", {"events": []})
    assert provider.status.state == "ERROR"


def test_liquid_empty_content_is_a_visible_malformed_response(monkeypatch):
    response = {"choices": [{"message": {"content": None, "reasoning": "not persisted"}}]}
    monkeypatch.setattr("providers.liquid.urlopen", lambda request, timeout: FakeResponse(response))
    provider = LiquidProvider(api_key="openrouter_test")
    with pytest.raises(LiquidMalformedResponse):
        provider.compile("system", {"events": []})
    assert provider.status.state == "ERROR"


def test_non_liquid_openrouter_model_is_rejected_before_request():
    with pytest.raises(Exception, match="actual OpenRouter liquid"):
        LiquidProvider(api_key="openrouter_test", model="openai/gpt-4o-mini")
