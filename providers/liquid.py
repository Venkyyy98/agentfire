"""Liquid AI provider via OpenRouter, used only for experience compilation."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LiquidError(RuntimeError):
    pass


class LiquidNotConfigured(LiquidError):
    pass


class LiquidMalformedResponse(LiquidError):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    state: str
    detail: str


EXPERIENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "symptoms": {"type": "array", "items": {"type": "string"}},
        "root_cause": {"type": "string"},
        "strong_evidence": {"type": "array", "items": {"type": "string"}},
        "successful_fix": {"type": "array", "items": {"type": "string"}},
        "failed_actions": {"type": "array", "items": {"type": "string"}},
        "reusable_lesson": {"type": "string"},
        "do_not_assume": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["symptoms", "root_cause", "strong_evidence", "successful_fix",
                 "failed_actions", "reusable_lesson", "do_not_assume", "confidence"],
    "additionalProperties": False,
}


class LiquidProvider:
    """Minimal OpenAI-compatible client restricted to real Liquid model IDs."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL",
                                               "https://openrouter.ai/api/v1")).rstrip("/")
        self.model = model or os.getenv("LIQUID_MODEL", "liquid/lfm-2.5-2.6b:free")
        self._status = (ProviderStatus("NOT_CONFIGURED", "OPENROUTER_API_KEY is missing")
                        if not self.api_key else ProviderStatus("ERROR", "Not yet authenticated"))
        if not self.api_key:
            raise LiquidNotConfigured(
                "Liquid compilation via OpenRouter requires OPENROUTER_API_KEY; no fallback was used")
        if not self.model.startswith("liquid/"):
            raise LiquidError("LIQUID_MODEL must be an actual OpenRouter liquid/... model; no request sent")

    @property
    def status(self) -> ProviderStatus:
        return self._status

    def compile(self, system_prompt: str, incident_payload: dict) -> dict:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(incident_payload, separators=(",", ":"))},
            ],
            "temperature": 0,
            # LFM2.5 reasoning is mandatory and counts against this budget. Keep its private reasoning
            # out of the response and reserve ample room for the small final JSON object.
            "max_tokens": 2400,
            "reasoning": {"max_tokens": 900, "exclude": True},
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "agentfire_durable_experience", "strict": True,
                "schema": EXPERIENCE_SCHEMA,
            }},
            "provider": {"require_parameters": True},
        }
        response = self._request("/chat/completions", body)
        try:
            content = response["choices"][0]["message"]["content"]
            result = _parse_json_object(content)
        except (AttributeError, KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            self._status = ProviderStatus("ERROR", "Liquid returned malformed structured output")
            raise LiquidMalformedResponse("Liquid returned malformed structured output") from error
        self._status = ProviderStatus(
            "CONNECTED", f"Authenticated OpenRouter inference using Liquid model {self.model}")
        return result

    def _request(self, path: str, body: dict) -> dict:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "User-Agent": "AgentFire/0.3"},
        )
        try:
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode())
        except HTTPError as error:
            self._status = ProviderStatus("ERROR", f"Liquid HTTP {error.code}")
            detail = error.read().decode()[:500]
            raise LiquidError(f"Liquid HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError) as error:
            self._status = ProviderStatus("ERROR", f"Liquid connection failed: {error}")
            raise LiquidError(f"Liquid connection failed: {error}") from error


def _parse_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise json.JSONDecodeError("expected JSON object", text, 0)
    return result
