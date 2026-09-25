# AgentFire

AgentFire runs Incident #1 with either a real OpenAI tool-calling agent or deterministic fallback.
Every run keeps a local audit trail. `EVENT_BACKEND=rawtree` sends schema-free flight-recorder events to
RawTree (the recommended Tinybird-product integration), while `EVENT_BACKEND=tinybird` retains the standard
Tinybird Events API path. Both fail visibly when explicitly selected and unavailable.

```bash
python3 -m pytest -q
AGENT_MODE=fallback EVENT_BACKEND=local python3 app.py
```

Raw events remain append-only in `EventStore`; the agent receives only `ActiveState` plus tool observations.

RawTree mode requires `RAWTREE_API_KEY`; `RAWTREE_URL` defaults to `https://api.rawtree.com`. The database,
events table, and memories table are configurable with `RAWTREE_DATABASE`, `RAWTREE_EVENTS_TABLE`, and
`RAWTREE_MEMORIES_TABLE`. RawTree creates the schema-free tables on first successful insert.

Tinybird mode requires `TINYBIRD_TOKEN` with append access to `agentfire_events` and read access for SQL
queries. Set `TINYBIRD_HOST` to the API host for the workspace region. Datasource names can be overridden
with `TINYBIRD_EVENTS_DATASOURCE` and `TINYBIRD_MEMORIES_DATASOURCE`.

## Phase 3 experience compiler

The compiler reads a completed run from RawTree, sends only observable incident events and deterministic
evaluation metadata to an actual Liquid model through OpenRouter, validates the compact memory, stores it
in RawTree, and records compilation lifecycle events. It never sends or stores private chain-of-thought.

Configure `OPENROUTER_API_KEY` and optionally override `LIQUID_MODEL` (which must begin with `liquid/`).
The default is the free compact extraction-capable model `liquid/lfm-2.5-2.6b:free`.

```bash
python3 compile_experience.py RUN-cbc2e587b04f
```

The optional `--compiler fallback` mode is deterministic demo insurance and its stored memory is explicitly
labeled `source=fallback`; it is never reported as Liquid.
