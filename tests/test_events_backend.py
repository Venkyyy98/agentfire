import pytest

from events import EventStore, LocalEventBackend
from providers.tinybird import TinybirdEventBackend, TinybirdNotConfigured, parse_analytics_response


def test_local_backend_preserves_and_serializes_events():
    store = EventStore(run_id="RUN-1", shift_id="SHIFT-1", agent_mode="llm", provider_mode="local")
    event = store.record("03:14", "tool_call", tool="get_metrics", service="payment")
    row = store.serialize(event)
    assert len(store.events) == 1
    assert row["run_id"] == "RUN-1"
    assert row["simulated_time"] == "03:14"
    assert row["tool_name"] == "get_metrics"
    assert row["provider_mode"] == "local"
    assert store.flush()["mode"] == "LOCAL"


def test_tinybird_mode_missing_token_is_visible(monkeypatch):
    monkeypatch.delenv("TINYBIRD_TOKEN", raising=False)
    with pytest.raises(TinybirdNotConfigured, match="requires TINYBIRD_TOKEN"):
        TinybirdEventBackend(token="")


def test_tinybird_serialization_can_be_buffered_without_network():
    backend = TinybirdEventBackend(token="test-token", host="https://example.invalid")
    backend.append({"run_id": "R", "event_type": "tool_call"})
    assert backend._pending == [{"run_id": "R", "event_type": "tool_call"}]
    assert backend.status.state == "ERROR"


def test_analytics_response_parsing():
    parsed = parse_analytics_response({"data": [{
        "event_count": "78", "incident_count": 1, "recovery_success_count": 1,
        "recovery_rate": 1, "verification_count": 1, "verification_rate": 1,
        "tool_call_count": 14, "remediation_count": 1, "unsafe_action_count": 0,
        "unnecessary_action_count": 0, "memory_retrieved_count": 0,
    }]})
    assert parsed["event_count"] == 78
    assert parsed["recovery_rate"] == 1.0
    assert parsed["tool_call_count"] == 14
