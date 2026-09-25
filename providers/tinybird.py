"""Tinybird Events API flight recorder, SQL analytics, and Phase 3 memory contract."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from memory import DurableExperience


class TinybirdError(RuntimeError):
    pass


class TinybirdNotConfigured(TinybirdError):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    state: str
    detail: str


class TinybirdEventBackend:
    def __init__(self, token: str | None = None, host: str | None = None,
                 events_datasource: str | None = None, memories_datasource: str | None = None) -> None:
        self.token = token or os.getenv("TINYBIRD_TOKEN", "")
        self.host = (host or os.getenv("TINYBIRD_HOST", "https://api.tinybird.co")).rstrip("/")
        self.events_datasource = events_datasource or os.getenv("TINYBIRD_EVENTS_DATASOURCE", "agentfire_events")
        self.memories_datasource = memories_datasource or os.getenv("TINYBIRD_MEMORIES_DATASOURCE", "agentfire_memories")
        self._pending: list[dict] = []
        self._status = ProviderStatus("NOT_CONFIGURED", "TINYBIRD_TOKEN is missing") if not self.token else ProviderStatus("ERROR", "Not yet authenticated")
        if not self.token:
            raise TinybirdNotConfigured("EVENT_BACKEND=tinybird requires TINYBIRD_TOKEN")

    @property
    def status(self) -> ProviderStatus:
        return self._status

    def append(self, event: dict) -> None:
        self._pending.append(event)

    def flush(self) -> dict:
        if not self._pending:
            return {"successful_rows": 0}
        rows = list(self._pending)
        body = "\n".join(json.dumps(row, separators=(",", ":")) for row in rows).encode()
        result = self._request("POST", "/v0/events", query={"name": self.events_datasource, "wait": "true"},
                               body=body, content_type="application/x-ndjson")
        self._pending.clear()
        self._status = ProviderStatus("CONNECTED", f"Authenticated ingestion to {self.events_datasource}")
        return {"successful_rows": len(rows), "response": result}

    def healthcheck(self) -> ProviderStatus:
        self._sql("SELECT 1 AS ok FORMAT JSON")
        self._status = ProviderStatus("CONNECTED", "Authenticated Tinybird query succeeded")
        return self._status

    def query_run_events(self, run_id: str) -> list[dict]:
        safe = _sql_string(run_id)
        result = self._sql(
            f"SELECT * FROM {self.events_datasource} WHERE run_id = '{safe}' ORDER BY timestamp, sequence FORMAT JSON"
        )
        return result.get("data", [])

    def query_reliability(self, run_id: str | None = None) -> dict:
        where = f" WHERE run_id = '{_sql_string(run_id)}'" if run_id else ""
        query = f"""SELECT
count() AS event_count,
uniqExactIf(incident_id, event_type = 'incident_injected') AS incident_count,
countIf(event_type = 'scenario_finished' AND status = 'passed') AS recovery_success_count,
if(incident_count = 0, 0, recovery_success_count / incident_count) AS recovery_rate,
countIf(event_type = 'scenario_finished' AND classification = 'verified') AS verification_count,
if(incident_count = 0, 0, verification_count / incident_count) AS verification_rate,
countIf(event_type = 'tool_call') AS tool_call_count,
countIf(event_type = 'remediation') AS remediation_count,
sumIf(JSONExtractUInt(payload_json, 'unsafe_action_count'), event_type = 'scenario_finished') AS unsafe_action_count,
sumIf(JSONExtractUInt(payload_json, 'unnecessary_action_count'), event_type = 'scenario_finished') AS unnecessary_action_count,
countIf(event_type = 'memory_retrieved') AS memory_retrieved_count
FROM {self.events_datasource}{where} FORMAT JSON"""
        return parse_analytics_response(self._sql(query))

    def store_experience(self, experience: DurableExperience) -> dict:
        body = json.dumps(experience.as_dict(), separators=(",", ":")).encode()
        return self._request("POST", "/v0/events",
                             query={"name": self.memories_datasource, "wait": "true"},
                             body=body, content_type="application/x-ndjson")

    def query_similar_experiences(self, query_text: str, limit: int = 3) -> list[dict]:
        term = _sql_string(query_text)
        query = f"""SELECT * FROM {self.memories_datasource}
WHERE positionCaseInsensitive(concat(root_cause, ' ', reusable_lesson, ' ', do_not_assume), '{term}') > 0
ORDER BY confidence DESC, created_at DESC LIMIT {max(1, min(limit, 20))} FORMAT JSON"""
        return self._sql(query).get("data", [])

    def _sql(self, query: str) -> dict:
        return self._request("POST", "/v0/sql", body=query.encode(), content_type="text/plain")

    def _request(self, method: str, path: str, query: dict | None = None,
                 body: bytes | None = None, content_type: str = "application/json") -> dict:
        url = f"{self.host}{path}"
        if query:
            url += "?" + urlencode(query)
        request = Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": content_type,
            "User-Agent": "AgentFire/0.2",
        })
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as error:
            self._status = ProviderStatus("ERROR", f"Tinybird HTTP {error.code}")
            detail = error.read().decode()[:500]
            raise TinybirdError(f"Tinybird HTTP {error.code}: {detail}") from error
        except URLError as error:
            self._status = ProviderStatus("ERROR", f"Tinybird connection failed: {error.reason}")
            raise TinybirdError(f"Tinybird connection failed: {error.reason}") from error


def _sql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def parse_analytics_response(response: dict) -> dict:
    data = response.get("data", [])
    if not data:
        return {}
    row = data[0]
    return {
        "event_count": int(row.get("event_count", 0)),
        "incident_count": int(row.get("incident_count", 0)),
        "recovery_success_count": int(row.get("recovery_success_count", 0)),
        "recovery_rate": float(row.get("recovery_rate", 0)),
        "verification_count": int(row.get("verification_count", 0)),
        "verification_rate": float(row.get("verification_rate", 0)),
        "tool_call_count": int(row.get("tool_call_count", 0)),
        "remediation_count": int(row.get("remediation_count", 0)),
        "unsafe_action_count": int(row.get("unsafe_action_count", 0)),
        "unnecessary_action_count": int(row.get("unnecessary_action_count", 0)),
        "memory_retrieved_count": int(row.get("memory_retrieved_count", 0)),
    }
