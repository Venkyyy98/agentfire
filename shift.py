"""One continuous 24-hour endurance shift; Phase 1 executes only Incident #1."""
from __future__ import annotations

from agent import DeterministicAgent
from evaluator import evaluate
from events import EventStore
from memory_retrieval import retrieve_for_incident
from scenarios import INCIDENT_1, INCIDENT_2
from simulator import ProductionSimulator
from state import ActiveState


def _event_backend(mode: str):
    if mode == "local":
        return None
    if mode == "tinybird":
        from providers.tinybird import TinybirdEventBackend
        return TinybirdEventBackend()
    if mode == "rawtree":
        from providers.rawtree import RawTreeEventBackend
        return RawTreeEventBackend()
    raise ValueError("EVENT_BACKEND must be 'local', 'rawtree', or 'tinybird'")


class EnduranceShift:
    def __init__(self, agent_mode: str = "fallback", provider=None, max_steps: int = 20,
                 event_backend: str = "local") -> None:
        if agent_mode not in {"fallback", "llm"}:
            raise ValueError("AGENT_MODE must be 'fallback' or 'llm'")
        self.agent_mode, self.provider, self.max_steps = agent_mode, provider, max_steps
        self.event_backend = event_backend
        backend = _event_backend(event_backend)
        self.events = EventStore(backend=backend, agent_mode=agent_mode, provider_mode=event_backend)
        self.simulator = ProductionSimulator()
        self.state = ActiveState(current_status=self.simulator.public_statuses())
        self.events.record("00:00", "shift_started", objective=self.state.objective)

    def run_incident_1(self) -> dict:
        self._normal_observations("00:00", 12)
        self.state.simulated_time = INCIDENT_1.starts_at
        self.state.active_incident = INCIDENT_1.incident_id
        self.simulator.inject(INCIDENT_1)
        self.events.set_incident(INCIDENT_1.incident_id)
        # The agent gets only the alert-visible blast radius initially. Other services are unknown
        # until its own selected observation tools query them.
        self.state.current_status = {"payment": "degraded", "checkout": "degraded", "auth": "unknown",
                                     "database": "unknown", "queue": "unknown"}
        before = self.state.snapshot()
        self.events.record(INCIDENT_1.starts_at, "incident_injected", incident_id=INCIDENT_1.incident_id,
                           visible_summary=INCIDENT_1.visible_summary)
        if self.agent_mode == "llm":
            from llm_agent import LLMAgent
            agent = LLMAgent(self.simulator, self.events, self.state, self.provider, self.max_steps)
        else:
            agent = DeterministicAgent(self.simulator, self.events, self.state)
        trace = agent.resolve_active_incident()
        self.state.current_status = self.simulator.public_statuses()
        self.state.active_incident = None
        result = evaluate(INCIDENT_1, self.simulator, trace, len(self.events.events) + 1)
        self.events.record("03:21", "scenario_finished", incident_id=INCIDENT_1.incident_id,
                           status="passed" if result["pass"] else "failed",
                           classification="verified" if result["verification_performed"] else "unverified",
                           recovery_success=result["recovery_success"],
                           unsafe_action_count=len(result["dangerous_actions"]),
                           unnecessary_action_count=len(result["unnecessary_actions"]))
        self.events.flush()
        backend_status = getattr(self.events.backend, "status", None)
        provider_status = ({"state": backend_status.state, "detail": backend_status.detail}
                           if backend_status else {"state": "LOCAL", "detail": "In-memory local event backend"})
        return {"trace": trace, "before_state": before, "mid_state": agent.mid_investigation_state,
                "after_state": self.state.snapshot(), "evaluation": result,
                "run_id": self.events.run_id, "event_backend": self.event_backend,
                "provider_status": provider_status}

    def run_incident_2(self, memory_backend=None) -> dict:
        """Run later in the same logical shift, retrieving compact prior experience by live symptoms."""
        self.state.simulated_time = "18:40"
        self.events.record("18:40", "scenario_started", incident_id=INCIDENT_2.incident_id,
                           continuity="later_in_same_simulated_shift")
        self.state.simulated_time = INCIDENT_2.starts_at
        self.state.active_incident = INCIDENT_2.incident_id
        self.simulator.inject(INCIDENT_2)
        self.events.set_incident(INCIDENT_2.incident_id)
        self.state.current_status = {"payment": "degraded", "checkout": "degraded", "auth": "unknown",
                                     "database": "unknown", "queue": "unknown"}
        before = self.state.snapshot()
        self.events.record(INCIDENT_2.starts_at, "incident_injected", incident_id=INCIDENT_2.incident_id,
                           visible_summary=INCIDENT_2.visible_summary)

        backend = memory_backend or self.events.backend
        retrieved = None
        if hasattr(backend, "query_similar_experiences") and hasattr(backend, "query_run_events"):
            # Query uses only the visible blast radius; source raw events remain outside LLM context.
            retrieved = retrieve_for_incident(backend, INCIDENT_2.visible_summary)
        memory_context: list[dict] = []
        if retrieved:
            self.state.retrieved_experience = [retrieved.compact["memory_id"]]
            if retrieved.source_shift_id:
                self.events.shift_id = retrieved.source_shift_id
            memory_context = [retrieved.compact]
            self.events.record(INCIDENT_2.starts_at, "memory_retrieved",
                               memory_id=retrieved.compact["memory_id"],
                               source_run_id=retrieved.compact["source_run_id"],
                               raw_event_count=retrieved.raw_event_count,
                               raw_history_bytes=retrieved.raw_history_bytes,
                               estimated_raw_tokens=retrieved.estimated_raw_tokens,
                               durable_memory_bytes=retrieved.memory_bytes,
                               estimated_durable_memory_tokens=retrieved.estimated_memory_tokens)

        if self.agent_mode == "llm":
            from llm_agent import LLMAgent
            agent = LLMAgent(self.simulator, self.events, self.state, self.provider, self.max_steps,
                             durable_experience=memory_context)
        else:
            agent = DeterministicAgent(self.simulator, self.events, self.state)
        trace = agent.resolve_active_incident()
        self.state.current_status = self.simulator.public_statuses()
        self.state.active_incident = None
        result = evaluate(INCIDENT_2, self.simulator, trace, len(self.events.events) + 2,
                          memory_retrieved=bool(retrieved),
                          previous_hypothesis_checked=self.state.prior_hypothesis_checked,
                          previous_hypothesis_rejected=self.state.prior_hypothesis_rejected)
        self.events.record("18:57", "memory_effect_evaluated", incident_id=INCIDENT_2.incident_id,
                           memory_id=retrieved.compact["memory_id"] if retrieved else "",
                           memory_effect=result["memory_effect"],
                           previous_hypothesis_checked=result["previous_hypothesis_checked"],
                           previous_hypothesis_rejected=result["previous_hypothesis_rejected"])
        self.events.record("18:57", "scenario_finished", incident_id=INCIDENT_2.incident_id,
                           status="passed" if result["pass"] else "failed",
                           classification="verified" if result["verification_performed"] else "unverified",
                           recovery_success=result["recovery_success"],
                           unsafe_action_count=len(result["dangerous_actions"]),
                           unnecessary_action_count=len(result["unnecessary_actions"]),
                           memory_effect=result["memory_effect"])
        self.events.flush()
        backend_status = getattr(self.events.backend, "status", None)
        provider_status = ({"state": backend_status.state, "detail": backend_status.detail}
                           if backend_status else {"state": "LOCAL", "detail": "In-memory local event backend"})
        return {"trace": trace, "before_state": before, "mid_state": agent.mid_investigation_state,
                "after_state": self.state.snapshot(), "evaluation": result, "run_id": self.events.run_id,
                "event_backend": self.event_backend, "provider_status": provider_status,
                "retrieved_memory": retrieved.compact if retrieved else None,
                "context_metrics": retrieved}

    def _normal_observations(self, time: str, count: int) -> None:
        for index in range(count):
            self.events.record(time, "normal_observation", sequence_in_window=index + 1,
                               statuses=self.simulator.public_statuses())

    @property
    def scenario_2_defined(self) -> bool:
        return INCIDENT_2.incident_id == "INC-002"
