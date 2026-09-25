import json

import pytest

from experience_compiler import ExperienceCompiler, calculate_compaction
from memory import DurableExperience
from providers.liquid import ProviderStatus


LIQUID_FIELDS = {
    "symptoms": ["Payment degraded", "Checkout degraded", "HTTP 401 responses"],
    "root_cause": "Expired credentials in shared authentication",
    "strong_evidence": ["Auth logs reported expired credentials"],
    "successful_fix": ["Refreshed auth credentials", "Verified services"],
    "failed_actions": [],
    "reusable_lesson": "Correlated HTTP 401 failures may indicate a shared authentication dependency.",
    "do_not_assume": "Do not assume recurrence; verify current authentication health first.",
    "confidence": 0.94,
}


class FakeLiquid:
    status = ProviderStatus("CONNECTED", "test")

    def compile(self, system_prompt, payload):
        assert "private reasoning" in system_prompt
        assert payload["source_run_id"] == "RUN-1"
        return LIQUID_FIELDS


class FakeBackend:
    status = type("Status", (), {"state": "CONNECTED", "detail": "test"})()

    def __init__(self):
        self.rows = [{
            "run_id": "RUN-1", "incident_id": "INC-001", "sequence": 1,
            "event_type": "incident_injected", "payload_json": json.dumps({"visible": "payment down"}),
        }, {
            "run_id": "RUN-1", "incident_id": "INC-001", "sequence": 2,
            "event_type": "scenario_finished", "status": "passed",
            "payload_json": json.dumps({"recovery_success": True}),
        }]
        self.pending = []
        self.stored = []

    def query_run_events(self, run_id):
        return self.rows if run_id == "RUN-1" else []

    def append(self, event):
        self.pending.append(event)

    def flush(self):
        return {"inserted": len(self.pending)}

    def store_experience(self, memory):
        self.stored.append(memory.as_dict())
        return {"inserted": 1}


def test_rawtree_liquid_rawtree_compilation_contract():
    backend = FakeBackend()
    result = ExperienceCompiler(backend, provider=FakeLiquid()).compile_run("RUN-1")
    memory = result["memory"]
    assert memory.source == "liquid"
    assert memory.source_run_id == "RUN-1"
    assert backend.stored[0]["memory_id"] == memory.memory_id
    assert [row["event_type"] for row in backend.pending] == [
        "experience_compilation_started", "experience_compilation_completed", "experience_stored"]


def test_malformed_liquid_schema_is_not_silently_replaced():
    class MalformedLiquid(FakeLiquid):
        def compile(self, system_prompt, payload):
            return {"root_cause": "auth"}

    with pytest.raises(ValueError, match="invalid Liquid schema"):
        ExperienceCompiler(FakeBackend(), provider=MalformedLiquid()).compile_run("RUN-1")


def test_compaction_metrics_are_calculated_from_serialized_values():
    raw = [{"event_type": "tool_result", "payload": "x" * 1000}]
    memory = DurableExperience(memory_id="MEM-1", incident_id="INC-1", root_cause="auth",
                               reusable_lesson="401 may indicate auth", do_not_assume="Verify auth",
                               source_run_id="RUN-1")
    metrics = calculate_compaction(raw, memory)
    assert metrics.raw_event_count == 1
    assert metrics.raw_bytes > metrics.compiled_bytes
    assert metrics.compression_ratio == round(metrics.raw_bytes / metrics.compiled_bytes, 2)


def test_fallback_is_explicitly_labeled_and_never_liquid():
    result = ExperienceCompiler(FakeBackend(), compiler_mode="fallback").compile_run("RUN-1")
    assert result["memory"].source == "fallback"
    assert result["provider_status"] is None
