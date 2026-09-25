"""Deterministic fallback agent retained as explicit demo insurance."""
from __future__ import annotations

from events import EventStore
from simulator import ProductionSimulator
from state import ActiveState


class DeterministicAgent:
    """A bounded autonomous tool loop adapted from the prior resolver's investigate/act/verify shape.

    It deliberately has no Scenario import and no access to simulator private state.
    """
    def __init__(self, simulator: ProductionSimulator, events: EventStore, state: ActiveState) -> None:
        self.simulator, self.events, self.state = simulator, events, state
        self.tool_trace: list[str] = []
        self.mid_investigation_state: dict | None = None

    def resolve_active_incident(self) -> list[str]:
        self._tool("get_metrics", "payment")
        payment_logs = self._tool("get_logs", "payment")
        dependencies = self._tool("get_dependencies", "payment")
        self.state.evidence.extend(["payment degraded", *payment_logs])
        self.state.open_questions = ["Which shared dependency explains payment and checkout errors?"]
        self._hypothesis("shared dependency failure", 0.58)
        self.mid_investigation_state = self.state.snapshot()
        self.events.record(self.state.simulated_time, "state_updated", state=self.mid_investigation_state)

        if "auth" in dependencies:
            auth_metrics = self._tool("get_metrics", "auth")
            auth_logs = self._tool("get_logs", "auth")
            self.state.evidence.extend(auth_logs)
            if auth_metrics.get("token_valid") is False or any("TOKEN_EXPIRED" in log for log in auth_logs):
                self._hypothesis("expired shared authentication credential", 0.96)
                self._tool("refresh_credentials", "auth")
            else:
                self._reject("shared authentication failure")
                self._tool("get_metrics", "database")
                self._tool("get_logs", "database")
                self._hypothesis("database connection exhaustion", 0.90)
                self._tool("recover_database_pool")

        self._tool("verify_service", "payment")
        self._tool("verify_service", "checkout")
        self.state.verification_status = "completed"
        self.events.record(self.state.simulated_time, "state_updated", state=self.state.snapshot())
        return self.tool_trace

    def _tool(self, tool: str, service: str | None = None):
        action = f"{tool}:{service}" if service else tool
        self.events.record(self.state.simulated_time, "tool_call", tool=tool, service=service)
        result = getattr(self.simulator, tool)(service) if service else getattr(self.simulator, tool)()
        self.events.record(self.state.simulated_time, "tool_result", tool=tool, service=service, result=result)
        self.tool_trace.append(action)
        if service and tool == "get_metrics":
            self.state.current_status[service] = result.get("status", "unknown")
        if service and tool == "verify_service":
            self.state.current_status[service] = result.get("status", "unknown")
        if tool in {"refresh_credentials", "recover_database_pool", "restart_service"}:
            self.state.actions_attempted.append(action)
            self.events.record(self.state.simulated_time, "remediation", action=action, result=result)
        return result

    def _hypothesis(self, cause: str, confidence: float) -> None:
        self.state.current_hypotheses.append({"cause": cause, "confidence": confidence, "status": "unverified"})
        self.events.record(self.state.simulated_time, "hypothesis_created", cause=cause, confidence=confidence)

    def _reject(self, cause: str) -> None:
        self.state.rejected_hypotheses.append(cause)
        self.events.record(self.state.simulated_time, "hypothesis_rejected", cause=cause)


# Backward-compatible name for the Phase 1 tests and imports.
IntelliOpsAgent = DeterministicAgent
