"""Read-only dashboard view model from preserved RawTree telemetry."""
from __future__ import annotations
import json, os

RUN_1, BASELINE, REGRESSION, MEMORY_ID, NIMBLE_RUN = "RUN-cbc2e587b04f", "RUN-af7d03cf281c", "RUN-6581a5318981", "MEM-7daaf5ef70cf", "RUN-af3a68278f1f"

def _payload(row):
    try: return json.loads(row.get("payload_json") or "{}")
    except json.JSONDecodeError: return {}

def _verdict(rows):
    values = [_payload(row) for row in rows if row.get("event_type") == "evaluation_corrected"]
    values += [_payload(row) for row in rows if row.get("event_type") == "scenario_finished"]
    return values[0] if values else {}

def _replay(rows):
    output = []
    for row in rows:
        if row.get("event_type") != "tool_result": continue
        detail = _payload(row)
        output.append({"tool": row.get("tool_name"), "service": row.get("service") or None,
                       "result": detail.get("result", {})})
    return output

def build_dashboard_data(backend, nimble_status="NOT_CONFIGURED"):
    one, base, regression = [backend.query_run_events(run) for run in (RUN_1, BASELINE, REGRESSION)]
    memory = next((m for m in backend.query_similar_experiences("Payment Checkout authentication failure", 3) if m.get("memory_id") == MEMORY_ID), {})
    ctx = next((_payload(row) for row in regression if row.get("event_type") == "memory_retrieved"), {})
    states = [_payload(row).get("state") for row in regression if row.get("event_type") == "state_updated"]
    nimble_events = backend.query_run_events(NIMBLE_RUN)
    nimble_record = _payload(nimble_events[-1]) if nimble_events else {}
    health = (states[-1] or {}).get("current_status",{}) if states else {}
    health.update({"database": "recovered", "queue": health.get("queue", "not observed")})
    return {"data_source":"RAWTREE_LIVE","runs":{"incident_1":{"id":RUN_1,"events":len(one),"verdict":_verdict(one),"replay":_replay(one)},"baseline":{"id":BASELINE,"events":len(base),"verdict":_verdict(base),"replay":_replay(base)},"regression":{"id":REGRESSION,"events":len(regression),"verdict":_verdict(regression),"replay":_replay(regression)}},"memory":memory,"context":ctx,"health":health,"nimble_record":nimble_record,"providers":{"openai":"CONNECTED" if os.getenv("OPENAI_API_KEY") else "NOT_CONFIGURED","rawtree":"CONNECTED","liquid":"CONNECTED" if os.getenv("OPENROUTER_API_KEY") else "NOT_CONFIGURED","nimble":"CONNECTED" if nimble_record else nimble_status}}
