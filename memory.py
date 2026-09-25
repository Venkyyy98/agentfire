"""Validated durable-experience contract for the Phase 3 Liquid compiler."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class DurableExperience:
    memory_id: str
    incident_id: str
    symptoms: list[str] = field(default_factory=list)
    root_cause: str = ""
    strong_evidence: list[str] = field(default_factory=list)
    successful_fix: list[str] = field(default_factory=list)
    failed_actions: list[str] = field(default_factory=list)
    reusable_lesson: str = ""
    do_not_assume: str = ""
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "liquid"
    source_run_id: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        required_text = {
            "memory_id": self.memory_id,
            "incident_id": self.incident_id,
            "root_cause": self.root_cause,
            "reusable_lesson": self.reusable_lesson,
            "do_not_assume": self.do_not_assume,
            "source": self.source,
            "source_run_id": self.source_run_id,
        }
        missing = [name for name, value in required_text.items() if not isinstance(value, str) or not value.strip()]
        if missing:
            raise ValueError(f"durable experience missing required fields: {', '.join(missing)}")
        for name in ("symptoms", "strong_evidence", "successful_fix", "failed_actions"):
            value = getattr(self, name)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"durable experience field {name} must be a list of strings")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("durable experience confidence must be between 0 and 1")
        uncertainty = ("may", "might", "could", "possible", "can indicate", "can suggest")
        if not any(marker in self.reusable_lesson.lower() for marker in uncertainty):
            raise ValueError("reusable_lesson must preserve uncertainty")
        safety = ("verify", "check", "confirm", "do not assume")
        if not any(marker in self.do_not_assume.lower() for marker in safety):
            raise ValueError("do_not_assume must require verification instead of automatic remediation")
