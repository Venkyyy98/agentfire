"""Append-only raw event history. This is deliberately separate from reasoning state."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class Event:
    sequence: int
    simulated_time: str
    event_type: str
    detail: dict


class LocalEventBackend:
    state = "LOCAL"

    def append(self, event: dict) -> None:
        pass

    def flush(self) -> dict:
        return {"successful_rows": 0, "mode": "LOCAL"}


class EventStore:
    def __init__(self, backend=None, run_id: str | None = None, shift_id: str | None = None,
                 agent_mode: str = "fallback", provider_mode: str = "local") -> None:
        self.events: list[Event] = []
        self.backend = backend or LocalEventBackend()
        self.run_id = run_id or f"RUN-{uuid.uuid4().hex[:12]}"
        self.shift_id = shift_id or f"SHIFT-{uuid.uuid4().hex[:12]}"
        self.agent_mode = agent_mode
        self.provider_mode = provider_mode
        self.incident_id = ""

    def record(self, simulated_time: str, event_type: str, **detail: object) -> Event:
        event = Event(len(self.events) + 1, simulated_time, event_type, dict(detail))
        self.events.append(event)
        self.backend.append(self.serialize(event))
        return event

    def set_incident(self, incident_id: str | None) -> None:
        self.incident_id = incident_id or ""

    def serialize(self, event: Event) -> dict:
        detail = event.detail
        return {
            "run_id": self.run_id,
            "shift_id": self.shift_id,
            "incident_id": detail.get("incident_id", self.incident_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulated_time": event.simulated_time,
            "sequence": event.sequence,
            "event_type": event.event_type,
            "service": detail.get("service") or "",
            "tool_name": detail.get("tool") or "",
            "action": detail.get("action") or "",
            "status": detail.get("status") or "",
            "classification": detail.get("classification") or "",
            "memory_id": detail.get("memory_id") or "",
            "recovery_success": bool(detail.get("recovery_success", False)),
            "verification_performed": detail.get("classification") == "verified",
            "unsafe_action_count": int(detail.get("unsafe_action_count", 0)),
            "unnecessary_action_count": int(detail.get("unnecessary_action_count", 0)),
            "payload_json": json.dumps(detail, separators=(",", ":"), sort_keys=True),
            "provider_mode": self.provider_mode,
            "agent_mode": self.agent_mode,
        }

    def flush(self) -> dict:
        return self.backend.flush()

    def as_dicts(self) -> list[dict]:
        return [asdict(event) for event in self.events]

    @property
    def estimated_tokens(self) -> int:
        """A labeled estimate for the dashboard; raw JSON characters / four."""
        return max(1, len(json.dumps(self.as_dicts())) // 4)
