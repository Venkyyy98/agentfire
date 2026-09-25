import pytest

from agent_tools import TOOL_SCHEMAS, ToolDispatcher
from events import EventStore
from llm_agent import LLMAgent, SYSTEM_PROMPT
from scenarios import INCIDENT_1
from simulator import ProductionSimulator
from state import ActiveState


class RepeatingProvider:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        return {"content": "", "tool_calls": [{
            "id": f"call-{self.calls}", "name": "get_metrics", "arguments": {"service": "payment"},
            "raw": {"id": f"call-{self.calls}", "type": "function",
                    "function": {"name": "get_metrics", "arguments": '{"service":"payment"}'}},
        }]}


def _parts():
    simulator = ProductionSimulator()
    simulator.inject(INCIDENT_1)
    events = EventStore()
    state = ActiveState(simulated_time="03:14", active_incident="INC-001",
                        current_status={"payment": "degraded", "checkout": "degraded", "auth": "unknown"})
    return simulator, events, state


def test_llm_receives_tool_schemas_and_stops_at_max_steps():
    simulator, events, state = _parts()
    provider = RepeatingProvider()
    agent = LLMAgent(simulator, events, state, provider=provider, max_steps=3)
    trace = agent.resolve_active_incident()
    assert trace == ["get_metrics:payment"] * 3
    assert provider.calls == 3
    assert events.events[-1].detail["status"] == "max_steps_reached"
    assert {tool["function"]["name"] for tool in TOOL_SCHEMAS} >= {"get_metrics", "verify_service"}


def test_tool_dispatch_rejects_unknown_tool():
    simulator, events, state = _parts()
    dispatcher = ToolDispatcher(simulator, events, state)
    with pytest.raises(ValueError, match="not allowed"):
        dispatcher.execute("read_hidden_root_cause", {})


def test_memory_safety_contract_is_general_and_evidence_first():
    policy = SYSTEM_PROMPT.lower()
    assert "historical evidence, not current truth" in policy
    assert "verify that current observations support" in policy
    assert "evidence-supported remediation" in policy
    for forbidden in ("inc-002", "auth is healthy", "database", "recover_database_pool"):
        assert forbidden not in policy
