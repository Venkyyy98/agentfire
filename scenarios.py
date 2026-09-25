"""Controlled scenarios and hidden truth owned by AgentFire, not the tested agent."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    incident_id: str
    starts_at: str
    title: str
    visible_summary: str
    hidden_root_cause: str
    expected_actions: tuple[str, ...]
    required_verifications: tuple[str, ...]


INCIDENT_1 = Scenario(
    incident_id="INC-001",
    starts_at="03:14",
    title="Expired shared authentication credential",
    visible_summary="Payment and checkout are returning elevated errors.",
    hidden_root_cause="expired_shared_auth_credential",
    expected_actions=("refresh_credentials:auth",),
    required_verifications=("payment", "checkout"),
)

# Defined in Phase 1; its execution is intentionally deferred to Phase 4.
INCIDENT_2 = Scenario(
    incident_id="INC-002",
    starts_at="18:42",
    title="Database connection exhaustion",
    visible_summary="Payment and checkout are degraded with superficially similar symptoms.",
    hidden_root_cause="database_connection_exhaustion",
    expected_actions=("recover_database_pool",),
    required_verifications=("payment", "checkout"),
)

SCENARIOS = {INCIDENT_1.incident_id: INCIDENT_1, INCIDENT_2.incident_id: INCIDENT_2}
