"""Small OpenAI provider adapter, based on the existing IntelliOps call_llm_agentic loop."""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv

load_dotenv()


class OpenAIProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("LLM mode requires OPENAI_API_KEY; no silent fallback was performed")
        from openai import OpenAI
        self.client = OpenAI(api_key=key)
        self.model = model or os.getenv("AGENTFIRE_LLM_MODEL", "gpt-4o-mini")

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=600,
            timeout=30,
        )
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            calls.append({
                "id": call.id,
                "name": call.function.name,
                "arguments": json.loads(call.function.arguments or "{}"),
                "raw": call.model_dump(),
            })
        return {"content": message.content or "", "tool_calls": calls}
