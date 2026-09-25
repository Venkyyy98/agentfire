import pytest

from providers.rawtree import RawTreeEventBackend, RawTreeNotConfigured


def test_rawtree_mode_missing_key_is_visible(monkeypatch):
    monkeypatch.delenv("RAWTREE_API_KEY", raising=False)
    with pytest.raises(RawTreeNotConfigured, match="requires RAWTREE_API_KEY"):
        RawTreeEventBackend(api_key="")


def test_rawtree_buffers_schema_free_events_without_network():
    backend = RawTreeEventBackend(api_key="rt_test", url="https://example.invalid")
    event = {"run_id": "RUN-1", "event_type": "tool_call", "custom_future_field": {"nested": True}}
    backend.append(event)
    assert backend._pending == [event]
    assert backend.status.state == "ERROR"


def test_rawtree_uses_database_and_table_contract():
    backend = RawTreeEventBackend(api_key="rt_test", database="hackathon",
                                  events_table="agentfire_events", memories_table="agentfire_memories")
    assert backend.database == "hackathon"
    assert backend.events_table == "agentfire_events"
    assert backend.memories_table == "agentfire_memories"


def test_rawtree_memory_storage_and_ranked_keyword_query_contract(monkeypatch):
    backend = RawTreeEventBackend(api_key="rt_test", memories_table="agentfire_memories")
    calls = []
    monkeypatch.setattr(backend, "_request", lambda method, path, body=None: calls.append(
        {"method": method, "path": path, "body": body}) or {"data": []})
    from memory import DurableExperience
    memory = DurableExperience(memory_id="MEM-1", incident_id="INC-001", root_cause="auth",
                               reusable_lesson="401 may indicate auth", do_not_assume="Verify auth",
                               source_run_id="RUN-1")
    backend.store_experience(memory)
    backend.query_similar_experiences("Payment degraded Checkout degraded HTTP authentication-like failures", 1)
    assert calls[0]["path"] == "/v1/tables/agentfire_memories"
    assert calls[0]["body"][0]["source_run_id"] == "RUN-1"
    query = calls[1]["body"]["sql"]
    assert "payment" in query and "checkout" in query and "authenticationlike" in query
    assert "LIMIT 1" in query
