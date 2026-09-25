"""RawTree -> Liquid -> compact durable experience -> RawTree orchestration."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from events import EventStore
from memory import DurableExperience
from providers.liquid import LiquidProvider


SYSTEM_PROMPT = """You compile observable SRE incident telemetry into compact durable experience.
Return one JSON object only with exactly these fields:
symptoms (string array), root_cause (string), strong_evidence (string array),
successful_fix (string array), failed_actions (string array), reusable_lesson (string),
do_not_assume (string), confidence (number from 0 to 1).
Use only supplied observable events and deterministic evaluator metadata. Never invent private reasoning.
Preserve uncertainty: reusable_lesson MUST describe the observed diagnostic pattern using the literal word
"may", "might", or "could" and must never prescribe a fix from symptoms alone. For example: "Correlated
HTTP 401 failures may indicate a shared authentication dependency." do_not_assume must explicitly require
checking or verifying the current dependency before reusing remediation. failed_actions means only explicit
remediation tool actions that were attempted and did not work; return [] when there were none. Do not treat
pre-remediation symptoms or elapsed time as failed actions. Keep the entire object concise."""


@dataclass(frozen=True)
class CompactionMetrics:
    raw_event_count: int
    raw_bytes: int
    estimated_raw_tokens: int
    compiled_bytes: int
    estimated_compiled_tokens: int
    compression_ratio: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class ExperienceCompiler:
    def __init__(self, memory_backend, provider: LiquidProvider | None = None,
                 compiler_mode: str = "liquid") -> None:
        if compiler_mode not in {"liquid", "fallback"}:
            raise ValueError("compiler_mode must be 'liquid' or 'fallback'")
        self.backend = memory_backend
        self.compiler_mode = compiler_mode
        self.provider = provider

    def compile_run(self, source_run_id: str) -> dict:
        raw_events = self.backend.query_run_events(source_run_id)
        if not raw_events:
            raise ValueError(f"no RawTree events found for run {source_run_id}")
        incident_id = next((row.get("incident_id") for row in raw_events
                            if row.get("event_type") == "incident_injected"), "")
        compile_events = EventStore(backend=self.backend, agent_mode="experience_compiler",
                                    provider_mode="rawtree")
        compile_events.set_incident(incident_id)
        compile_events.record("post-incident", "experience_compilation_started",
                              source_run_id=source_run_id, raw_event_count=len(raw_events),
                              compiler=self.compiler_mode)
        observable = _observable_payload(raw_events, source_run_id, incident_id)
        if self.compiler_mode == "liquid":
            provider = self.provider or LiquidProvider()
            fields = provider.compile(SYSTEM_PROMPT, observable)
            source = "liquid"
            provider_status = provider.status
        else:
            fields = _fallback_compile(observable)
            source = "fallback"
            provider_status = None
        memory = _build_memory(fields, incident_id, source_run_id, source)
        metrics = calculate_compaction(raw_events, memory)
        compile_events.record("post-incident", "experience_compilation_completed",
                              source_run_id=source_run_id, memory_id=memory.memory_id,
                              source=source, **metrics.as_dict())
        self.backend.store_experience(memory)
        compile_events.record("post-incident", "experience_stored", source_run_id=source_run_id,
                              memory_id=memory.memory_id, storage="rawtree")
        compile_events.flush()
        return {"memory": memory, "metrics": metrics, "provider_status": provider_status,
                "compilation_run_id": compile_events.run_id}


def _observable_payload(events: list[dict], run_id: str, incident_id: str) -> dict:
    allowed = {"incident_injected", "tool_call", "tool_result", "remediation", "verification",
               "scenario_finished"}
    selected = []
    for row in events:
        if row.get("event_type") not in allowed:
            continue
        detail = row.get("payload_json", {})
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except json.JSONDecodeError:
                detail = {"unparsed_observation": detail[:500]}
        selected.append({"sequence": row.get("sequence"), "event_type": row.get("event_type"),
                         "service": row.get("service", ""), "tool": row.get("tool_name", ""),
                         "action": row.get("action", ""), "status": row.get("status", ""),
                         "detail": detail})
    return {"source_run_id": run_id, "incident_id": incident_id, "observable_events": selected}


def _build_memory(fields: dict, incident_id: str, run_id: str, source: str) -> DurableExperience:
    expected = {"symptoms", "root_cause", "strong_evidence", "successful_fix", "failed_actions",
                "reusable_lesson", "do_not_assume", "confidence"}
    if set(fields) != expected:
        missing, extra = expected - set(fields), set(fields) - expected
        raise ValueError(f"invalid Liquid schema; missing={sorted(missing)}, extra={sorted(extra)}")
    memory = DurableExperience(memory_id=f"MEM-{uuid.uuid4().hex[:12]}", incident_id=incident_id,
                               source=source, source_run_id=run_id, **fields)
    memory.validate()
    return memory


def calculate_compaction(raw_events: list[dict], memory: DurableExperience) -> CompactionMetrics:
    raw = json.dumps(raw_events, separators=(",", ":"), sort_keys=True).encode()
    compiled = json.dumps(memory.as_dict(), separators=(",", ":"), sort_keys=True).encode()
    return CompactionMetrics(len(raw_events), len(raw), max(1, len(raw) // 4), len(compiled),
                             max(1, len(compiled) // 4), round(len(raw) / max(1, len(compiled)), 2))


def _fallback_compile(payload: dict) -> dict:
    """Explicit demo insurance; never used or labeled as Liquid."""
    return {
        "symptoms": ["Payment degraded", "Checkout degraded", "HTTP 401 authentication failures"],
        "root_cause": "Expired credentials in the shared authentication dependency",
        "strong_evidence": ["Authentication logs reported expired credentials"],
        "successful_fix": ["Refreshed authentication credentials", "Verified dependent services"],
        "failed_actions": [],
        "reusable_lesson": "Correlated HTTP 401 failures may indicate a shared authentication dependency.",
        "do_not_assume": "Do not assume the same cause; verify current authentication health before remediation.",
        "confidence": 0.95,
    }
