"""LLM-visible simulator tools plus validated dispatch and compact state updates."""
from __future__ import annotations

import json

from events import EventStore
from simulator import ProductionSimulator
from state import ActiveState

SERVICES = ["payment", "checkout", "auth", "database", "queue"]


def _service_tool(name: str, description: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string", "enum": SERVICES}},
                "required": ["service"],
                "additionalProperties": False,
            },
        },
    }


TOOL_SCHEMAS = [
    _service_tool("get_metrics", "Observe current metrics and health for one service."),
    _service_tool("get_logs", "Read recent observable logs for one service."),
    _service_tool("get_dependencies", "List the direct dependencies of one service."),
    _service_tool("restart_service", "Restart one service. Use only with supporting evidence."),
    {
        "type": "function",
        "function": {
            "name": "refresh_credentials",
            "description": "Refresh the shared authentication credential when observable evidence supports an authentication problem.",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string", "enum": ["auth"]}},
                "required": ["service"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recover_database_pool",
            "description": "Recover an exhausted database connection pool. Use only with database evidence.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    _service_tool("verify_service", "Explicitly verify whether a service is healthy after remediation."),
]


class ToolDispatcher:
    ALLOWED = {item["function"]["name"] for item in TOOL_SCHEMAS}

    def __init__(self, simulator: ProductionSimulator, events: EventStore, state: ActiveState) -> None:
        self.simulator, self.events, self.state = simulator, events, state
        self.trace: list[str] = []
        self.verified_services: set[str] = set()

    def execute(self, tool: str, arguments: dict) -> dict | list:
        if tool not in self.ALLOWED:
            raise ValueError(f"Tool not allowed: {tool}")
        service = arguments.get("service")
        if tool != "recover_database_pool" and service not in SERVICES:
            raise ValueError(f"Valid service required for {tool}")
        if tool == "recover_database_pool" and arguments:
            raise ValueError("recover_database_pool accepts no arguments")

        action = f"{tool}:{service}" if service else tool
        self.events.record(self.state.simulated_time, "tool_selected", tool=tool, arguments=arguments)
        self.events.record(self.state.simulated_time, "tool_call", tool=tool, service=service)
        result = getattr(self.simulator, tool)(service) if service else getattr(self.simulator, tool)()
        self.events.record(self.state.simulated_time, "tool_result", tool=tool, service=service, result=result)
        self.trace.append(action)
        self._update_state(tool, service, result)
        return result

    def _update_state(self, tool: str, service: str | None, result: dict | list) -> None:
        if tool == "get_metrics" and service and isinstance(result, dict):
            self.state.current_status[service] = result.get("status", "unknown")
            self.state.evidence.append(f"{service} metrics: {json.dumps(result, sort_keys=True)}")
            if service == "auth" and result.get("token_valid") is False:
                self._hypothesis("expired shared authentication credential", 0.90)
            elif service == "auth" and result.get("token_valid") is True and self.state.retrieved_experience:
                self._prior_auth_checked()
            if service == "database" and result.get("connections") == result.get("max_connections"):
                self._hypothesis("database connection exhaustion", 0.90)
        elif tool == "get_logs" and service:
            self.state.evidence.append(f"{service} logs: {json.dumps(result)}")
            text = " ".join(result).lower() if isinstance(result, list) else str(result).lower()
            if "401" in text or "token_expired" in text:
                self._hypothesis("shared authentication failure", 0.75)
            if service == "auth" and "normal" in text and "no authentication failures" in text:
                self._prior_auth_checked()
                self._reject("shared authentication failure")
        elif tool == "get_dependencies" and service:
            self.state.evidence.append(f"{service} dependencies: {json.dumps(result)}")
        elif tool in {"restart_service", "refresh_credentials", "recover_database_pool"}:
            action = f"{tool}:{service}" if service else tool
            self.state.actions_attempted.append(action)
            self.events.record(self.state.simulated_time, "remediation", action=action, result=result)
        elif tool == "verify_service" and service and isinstance(result, dict):
            self.state.current_status[service] = result.get("status", "unknown")
            self.verified_services.add(service)
            self.events.record(self.state.simulated_time, "verification", service=service,
                               healthy=result.get("healthy", False))

        required = {"payment", "checkout"}
        if required.issubset(self.verified_services):
            self.state.verification_status = "completed"
        self.events.record(self.state.simulated_time, "state_updated", state=self.state.snapshot())

    def _hypothesis(self, cause: str, confidence: float) -> None:
        if not any(item["cause"] == cause for item in self.state.current_hypotheses):
            self.state.current_hypotheses.append({"cause": cause, "confidence": confidence, "status": "unverified"})
            self.events.record(self.state.simulated_time, "hypothesis_created", cause=cause, confidence=confidence)

    def _reject(self, cause: str) -> None:
        if cause not in self.state.rejected_hypotheses:
            self.state.rejected_hypotheses.append(cause)
            self.events.record(self.state.simulated_time, "hypothesis_rejected", cause=cause)

    def _prior_auth_checked(self) -> None:
        """An observable healthy Auth read is evidence against a retrieved Auth hypothesis."""
        self.state.prior_hypothesis_checked = True
        if not self.state.prior_hypothesis_rejected:
            self.state.prior_hypothesis_rejected = True
            self._reject("shared authentication failure")
