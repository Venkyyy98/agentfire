import json

from evaluator import evaluate
from scenarios import INCIDENT_2
from shift import EnduranceShift
from simulator import ProductionSimulator


MEMORY = {
    "memory_id": "MEM-7daaf5ef70cf", "incident_id": "INC-001",
    "symptoms": ["Payment degraded", "Checkout degraded", "HTTP 401 failures"],
    "root_cause": "Authentication credential expiration",
    "strong_evidence": ["Auth token expired"], "successful_fix": ["refresh_credentials:auth"],
    "failed_actions": [], "reusable_lesson": "HTTP 401 failures may indicate shared authentication.",
    "do_not_assume": "Verify auth health before remediation.", "confidence": 0.95,
    "source": "liquid", "source_run_id": "RUN-cbc2e587b04f",
}


class MemoryBackend:
    status = type("Status", (), {"state": "CONNECTED", "detail": "fake"})()

    def __init__(self):
        self.pending = []

    def append(self, event):
        self.pending.append(event)

    def flush(self):
        return {"inserted": len(self.pending)}

    def query_similar_experiences(self, query, limit=1):
        assert "payment" in query.lower() and "checkout" in query.lower()
        return [MEMORY]

    def query_run_events(self, run_id):
        assert run_id == MEMORY["source_run_id"]
        return [{"shift_id": "SHIFT-PREVIOUS", "raw_marker": "DO_NOT_REPLAY"}] * 71


class ObservableGoodProvider:
    def __init__(self):
        self.index = 0
        self.messages = []
        self.calls = [
            ("get_metrics", {"service": "auth"}),
            ("get_metrics", {"service": "database"}),
            ("recover_database_pool", {}),
            ("verify_service", {"service": "payment"}),
            ("verify_service", {"service": "checkout"}),
        ]

    def complete(self, messages, tools):
        self.messages = messages
        name, arguments = self.calls[self.index]
        self.index += 1
        return {"content": "", "tool_calls": [{
            "id": f"call-{self.index}", "name": name, "arguments": arguments,
            "raw": {"id": f"call-{self.index}", "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)}},
        }]}


def test_incident_two_has_hidden_db_truth_with_healthy_auth():
    simulator = ProductionSimulator()
    simulator.inject(INCIDENT_2)
    assert simulator.get_metrics("auth")["token_valid"] is True
    assert simulator.get_metrics("database")["connections"] == 100
    assert simulator.get_metrics("database")["max_connections"] == 100
    assert simulator.refresh_credentials("auth")["recovered"] is False
    assert simulator.recover_database_pool()["recovered"] is True


def test_incident_two_retrieves_compact_memory_and_classifies_rejection():
    backend = MemoryBackend()
    provider = ObservableGoodProvider()
    shift = EnduranceShift(agent_mode="llm", provider=provider, event_backend="local", max_steps=5)
    run = shift.run_incident_2(memory_backend=backend)
    assert run["retrieved_memory"]["memory_id"] == "MEM-7daaf5ef70cf"
    assert run["evaluation"]["pass"] is True
    assert run["evaluation"]["memory_effect"] == "CORRECTLY_REJECTED"
    assert run["evaluation"]["previous_hypothesis_checked"] is True
    assert run["evaluation"]["previous_hypothesis_rejected"] is True
    context = provider.messages[1]["content"]
    assert "MEM-7daaf5ef70cf" in context
    assert "DO_NOT_REPLAY" not in context
    assert run["context_metrics"].raw_event_count == 71
    assert [event.detail["event_type"] if False else event.event_type for event in shift.events.events if event.event_type in {
        "memory_retrieved", "memory_effect_evaluated"}] == ["memory_retrieved", "memory_effect_evaluated"]


def test_blind_old_auth_remediation_is_objectively_misled_and_fails_usefulness():
    simulator = ProductionSimulator()
    simulator.inject(INCIDENT_2)
    simulator.refresh_credentials("auth")
    simulator.recover_database_pool()
    trace = ["get_metrics:auth", "refresh_credentials:auth", "get_metrics:database",
             "recover_database_pool", "verify_service:payment", "verify_service:checkout"]
    result = evaluate(INCIDENT_2, simulator, trace, event_count=8, memory_retrieved=True,
                      previous_hypothesis_checked=True, previous_hypothesis_rejected=False)
    assert result["memory_effect"] == "MISLED"
    assert "refresh_credentials:auth" in result["unnecessary_actions"]
    assert result["recovery_success"] is True
    assert result["pass"] is False


def test_current_dependency_and_timeout_evidence_can_support_correct_rejection():
    simulator = ProductionSimulator()
    simulator.inject(INCIDENT_2)
    simulator.recover_database_pool()
    trace = ["get_metrics:auth", "get_logs:auth", "get_dependencies:payment", "get_logs:payment",
             "recover_database_pool", "verify_service:payment", "verify_service:checkout"]
    result = evaluate(INCIDENT_2, simulator, trace, event_count=8, memory_retrieved=True,
                      previous_hypothesis_checked=True, previous_hypothesis_rejected=True)
    assert result["memory_effect"] == "CORRECTLY_REJECTED"
    assert result["pass"] is True
