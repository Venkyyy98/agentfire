"""Manual Phase 4 entry point: later-shift misleading-memory test."""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from shift import EnduranceShift


def main() -> None:
    load_dotenv()
    shift = EnduranceShift(agent_mode=os.getenv("AGENT_MODE", "llm").lower(),
                           event_backend=os.getenv("EVENT_BACKEND", "rawtree").lower())
    run = shift.run_incident_2()
    metrics = run["context_metrics"]
    print(json.dumps({
        "run_id": run["run_id"], "event_provider": run["provider_status"],
        "memory_id": run["retrieved_memory"].get("memory_id") if run["retrieved_memory"] else None,
        "tool_trace": run["trace"], "evaluation": run["evaluation"],
        "context_management": metrics.__dict__ if metrics else None,
        "final_state": run["after_state"],
    }, indent=2))


if __name__ == "__main__":
    main()
