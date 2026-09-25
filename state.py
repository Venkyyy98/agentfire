"""Compact current state supplied to the agent, never the full raw event transcript."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ActiveState:
    objective: str = "Keep production healthy for a simulated 24-hour on-call shift."
    simulated_time: str = "00:00"
    active_incident: str | None = None
    current_status: dict[str, str] = field(default_factory=dict)
    current_hypotheses: list[dict] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    rejected_hypotheses: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    retrieved_experience: list[str] = field(default_factory=list)
    prior_hypothesis_checked: bool = False
    prior_hypothesis_rejected: bool = False
    actions_attempted: list[str] = field(default_factory=list)
    verification_status: str = "not_started"

    def snapshot(self) -> dict:
        return asdict(self)

    def estimated_tokens(self) -> int:
        return max(1, len(str(self.snapshot())) // 4)
