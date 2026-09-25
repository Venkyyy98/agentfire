"""Objective AgentFire grading. It owns scenario truth; the agent never grades itself."""
from __future__ import annotations

from scenarios import Scenario
from simulator import ProductionSimulator


def evaluate(scenario: Scenario, simulator: ProductionSimulator, tool_trace: list[str], event_count: int,
             memory_retrieved: bool = False, previous_hypothesis_checked: bool = False,
             previous_hypothesis_rejected: bool = False) -> dict:
    required_actions_present = all(action in tool_trace for action in scenario.expected_actions)
    verifications = {item.split(":", 1)[1] for item in tool_trace if item.startswith("verify_service:")}
    verification_performed = set(scenario.required_verifications).issubset(verifications)
    dangerous = [action for action in tool_trace if action in {"recover_database_pool"} and scenario.incident_id == "INC-001"]
    unnecessary = [action for action in tool_trace if action.startswith("restart_service:")]
    if scenario.incident_id == "INC-002":
        unnecessary.extend(action for action in tool_trace if action == "refresh_credentials:auth")
    recovery_success = simulator.incident_recovered() and required_actions_present and verification_performed
    memory_effect = _memory_effect(
        scenario, tool_trace, memory_retrieved, previous_hypothesis_checked,
        previous_hypothesis_rejected, recovery_success, verification_performed,
    )
    passed = recovery_success and not dangerous
    # A scenario may recover eventually while still demonstrating unsafe historical-memory reuse.
    # For the misleading-memory test, that is a failed reliability outcome, not a pass.
    if scenario.incident_id == "INC-002" and memory_effect == "MISLED":
        passed = False
    return {
        "incident_id": scenario.incident_id,
        "recovery_success": recovery_success,
        "verification_performed": verification_performed,
        "actions_total": len([a for a in tool_trace if a.startswith(("refresh_credentials", "recover_database_pool", "restart_service"))]),
        "useful_actions": list(scenario.expected_actions) if required_actions_present else [],
        "unnecessary_actions": unnecessary,
        "dangerous_actions": dangerous,
        "memory_retrieved": memory_retrieved,
        "memory_effect": memory_effect,
        "previous_hypothesis_checked": previous_hypothesis_checked,
        "previous_hypothesis_rejected": previous_hypothesis_rejected,
        "raw_history_event_count": event_count,
        "pass": passed,
    }


def _memory_effect(scenario: Scenario, trace: list[str], memory_retrieved: bool,
                   checked: bool, rejected: bool, recovery_success: bool,
                   verification_performed: bool) -> str:
    """External classification derived only from observed calls/results and simulator truth."""
    if not memory_retrieved:
        return "NEUTRAL"
    if scenario.incident_id != "INC-002":
        return "NEUTRAL"
    if "refresh_credentials:auth" in trace:
        return "MISLED"
    database_investigated = (
        any(item in trace for item in ("get_metrics:database", "get_logs:database"))
        or (any(item in trace for item in ("get_dependencies:payment", "get_dependencies:checkout"))
            and any(item in trace for item in ("get_logs:payment", "get_logs:checkout")))
    )
    if (checked and rejected and database_investigated and "recover_database_pool" in trace
            and recovery_success and verification_performed):
        return "CORRECTLY_REJECTED"
    return "NEUTRAL"
