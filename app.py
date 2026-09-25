"""Phase 1 command-line proof. A dashboard is intentionally deferred to Phase 6."""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from shift import EnduranceShift

load_dotenv()


def main() -> None:
    mode = os.getenv("AGENT_MODE", "fallback").lower()
    event_backend = os.getenv("EVENT_BACKEND", "local").lower()
    shift = EnduranceShift(agent_mode=mode, event_backend=event_backend)
    run = shift.run_incident_1()
    print(f"AgentFire Phase 2 — Incident #1 | agent={mode} | events={event_backend}")
    print("Run ID:", run["run_id"])
    print("Event provider:", json.dumps(run["provider_status"]))
    print("Tool trace:", " → ".join(run["trace"]))
    print("Evaluator:", json.dumps(run["evaluation"], indent=2))
    print(f"Raw history: {len(shift.events.events)} events, ~{shift.events.estimated_tokens} tokens (estimate)")


if __name__ == "__main__":
    main()
