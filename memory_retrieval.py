"""Compact durable-memory retrieval; raw flight-recorder history never enters agent context."""
from __future__ import annotations

import json
from dataclasses import dataclass


MEMORY_FIELDS = ("memory_id", "incident_id", "symptoms", "root_cause", "strong_evidence",
                 "successful_fix", "failed_actions", "reusable_lesson", "do_not_assume",
                 "confidence", "source", "source_run_id")


@dataclass(frozen=True)
class RetrievedMemory:
    compact: dict
    raw_event_count: int
    raw_history_bytes: int
    estimated_raw_tokens: int
    memory_bytes: int
    estimated_memory_tokens: int
    source_shift_id: str | None


def retrieve_for_incident(backend, observable_query: str) -> RetrievedMemory | None:
    """Search by current observable symptoms and return at most one compact experience."""
    matches = backend.query_similar_experiences(observable_query, limit=1)
    if not matches:
        return None
    compact = {field: matches[0].get(field) for field in MEMORY_FIELDS}
    source_events = backend.query_run_events(compact["source_run_id"])
    raw_bytes = len(json.dumps(source_events, separators=(",", ":"), sort_keys=True).encode())
    memory_bytes = len(json.dumps(compact, separators=(",", ":"), sort_keys=True).encode())
    return RetrievedMemory(
        compact=compact,
        raw_event_count=len(source_events), raw_history_bytes=raw_bytes,
        estimated_raw_tokens=max(1, raw_bytes // 4), memory_bytes=memory_bytes,
        estimated_memory_tokens=max(1, memory_bytes // 4),
        source_shift_id=source_events[0].get("shift_id") if source_events else None,
    )
