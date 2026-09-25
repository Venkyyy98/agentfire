"""RawTree flight recorder: schema-free raw events plus SQL reliability analytics."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from memory import DurableExperience
from providers.tinybird import parse_analytics_response


class RawTreeError(RuntimeError):
    pass


class RawTreeNotConfigured(RawTreeError):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    state: str
    detail: str


class RawTreeEventBackend:
    def __init__(self, api_key: str | None = None, url: str | None = None,
                 database: str | None = None, events_table: str | None = None,
                 memories_table: str | None = None) -> None:
        self.api_key = api_key or os.getenv("RAWTREE_API_KEY", "")
        self.url = (url or os.getenv("RAWTREE_URL", "https://api.rawtree.com")).rstrip("/")
        self.database = database or os.getenv("RAWTREE_DATABASE", "default")
        self.events_table = events_table or os.getenv("RAWTREE_EVENTS_TABLE", "agentfire_events")
        self.memories_table = memories_table or os.getenv("RAWTREE_MEMORIES_TABLE", "agentfire_memories")
        self._pending: list[dict] = []
        self._status = ProviderStatus("NOT_CONFIGURED", "RAWTREE_API_KEY is missing") if not self.api_key else ProviderStatus("ERROR", "Not yet authenticated")
        if not self.api_key:
            raise RawTreeNotConfigured("EVENT_BACKEND=rawtree requires RAWTREE_API_KEY")

    @property
    def status(self) -> ProviderStatus:
        return self._status

    def append(self, event: dict) -> None:
        self._pending.append(event)

    def flush(self) -> dict:
        if not self._pending:
            return {"inserted": 0}
        rows = list(self._pending)
        result = self._request("POST", f"/v1/tables/{self.events_table}", body=rows)
        self._pending.clear()
        inserted = result.get("inserted", len(rows))
        self._status = ProviderStatus("CONNECTED", f"Authenticated RawTree ingestion to {self.events_table}")
        return {"successful_rows": inserted, "response": result}

    def healthcheck(self) -> ProviderStatus:
        self._query("SELECT 1 AS ok")
        self._status = ProviderStatus("CONNECTED", "Authenticated RawTree query succeeded")
        return self._status

    def query_run_events(self, run_id: str) -> list[dict]:
        safe = _sql_string(run_id)
        result = self._query(
            f"SELECT * FROM {self.events_table} WHERE run_id = '{safe}' ORDER BY timestamp, sequence LIMIT 1000"
        )
        return result.get("data", [])

    def query_reliability(self, run_id: str | None = None) -> dict:
        where = f" WHERE run_id = '{_sql_string(run_id)}'" if run_id else ""
        sql = f"""SELECT
count() AS event_count,
uniqExactIf(incident_id, event_type = 'incident_injected') AS incident_count,
countIf(event_type = 'scenario_finished' AND status = 'passed') AS recovery_success_count,
if(incident_count = 0, 0, recovery_success_count / incident_count) AS recovery_rate,
countIf(event_type = 'scenario_finished' AND classification = 'verified') AS verification_count,
if(incident_count = 0, 0, verification_count / incident_count) AS verification_rate,
countIf(event_type = 'tool_call') AS tool_call_count,
countIf(event_type = 'remediation') AS remediation_count,
sumIf(unsafe_action_count, event_type = 'scenario_finished') AS unsafe_action_count,
sumIf(unnecessary_action_count, event_type = 'scenario_finished') AS unnecessary_action_count,
countIf(event_type = 'memory_retrieved') AS memory_retrieved_count
FROM {self.events_table}{where}"""
        return parse_analytics_response(self._query(sql))

    def store_experience(self, experience: DurableExperience) -> dict:
        return self._request("POST", f"/v1/tables/{self.memories_table}", body=[experience.as_dict()])

    def query_similar_experiences(self, query_text: str, limit: int = 3) -> list[dict]:
        terms = [word for word in _search_terms(query_text) if len(word) >= 4][:10]
        if not terms:
            return []
        document = "concat(toString(symptoms), ' ', root_cause, ' ', toString(strong_evidence), ' ', reusable_lesson, ' ', do_not_assume)"
        matches = [f"positionCaseInsensitive({document}, '{_sql_string(term)}') > 0" for term in terms]
        score = " + ".join(f"toUInt8({match})" for match in matches)
        sql = f"""SELECT * FROM {self.memories_table}
WHERE {' OR '.join(matches)}
ORDER BY ({score}) DESC, confidence DESC, created_at DESC LIMIT {max(1, min(limit, 20))}"""
        return self._query(sql).get("data", [])

    def _query(self, sql: str) -> dict:
        return self._request("POST", "/v1/query", body={"sql": sql})

    def _request(self, method: str, path: str, body: object | None = None) -> dict:
        url = f"{self.url}{path}?{urlencode({'database': self.database})}"
        request = Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                          headers={"Authorization": f"Bearer {self.api_key}",
                                   "Content-Type": "application/json", "User-Agent": "AgentFire/0.2"})
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as error:
            self._status = ProviderStatus("ERROR", f"RawTree HTTP {error.code}")
            detail = error.read().decode()[:500]
            raise RawTreeError(f"RawTree HTTP {error.code}: {detail}") from error
        except URLError as error:
            self._status = ProviderStatus("ERROR", f"RawTree connection failed: {error.reason}")
            raise RawTreeError(f"RawTree connection failed: {error.reason}") from error


def _sql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _search_terms(value: str) -> list[str]:
    stop = {"with", "from", "that", "this", "failures", "degraded"}
    words = ["".join(character for character in raw.lower() if character.isalnum())
             for raw in value.split()]
    return list(dict.fromkeys(word for word in words if word and word not in stop))
