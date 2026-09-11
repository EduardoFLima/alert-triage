## Why

Capability slice 12 in [`docs/vision.md`](../../../docs/vision.md#circuit-breakers).
The `circuit_breakers` section has been resolved into `Config` since slice 1 and
read by nothing since. A multi-agent investigation can run away three ways —
inside one agent's tool loop, across the manager's consultations, or just by
running long — and today only the second is bounded, by a constant stated in an
adapter rather than by anything an operator can set.

Two of the five keys were also left undecided by slice 7 when ADK took ownership
of the MCP client. This slice settles them: one is wired, one is removed.

## What Changes

- **`max_agent_hops` becomes the manager's consultation budget**, which is what
  `MAX_CONSULTATIONS = 8` is today. A hop is the manager reaching a specialist,
  so the number of hops in an investigation is the number of consultations it
  made. **BREAKING**: its default moves from 2 to 8, since a bound of 2 would
  forbid the breadth the Diagnostician's instruction asks for.
  - Multi-hop dependency traversal is explicitly *not* what this key bounds.
    Treating it as a depth limit for a recursion no declaration can express
    would be a body written against a path nothing reaches.
- **`max_tool_calls_per_agent` becomes what it says**: how many MCP tool calls
  one specialist may make. Nothing bounds this today — a specialist with six
  tools and runtime discovery can loop indefinitely. It sits in
  `before_tool_callback`, the seat `log_tool_call` already occupies.
- **`max_investigation_duration_seconds` is enforced**, having been enforced
  nowhere. A deadline refuses further tool calls once passed, so a manager
  running long stops asking and still concludes; a wall-clock timeout around the
  run is the backstop for a model that hangs between calls.
- **`mcp_call_timeout_seconds` is wired** into the toolset's connection
  parameters, replacing the `CONNECT_TIMEOUT_SECONDS` / `READ_TIMEOUT_SECONDS`
  constants slice 7 stated there pending this slice.
- **`max_mcp_retries` is removed.** **BREAKING**: a deployment that sets it is
  refused by name at startup rather than left with a setting that does nothing.
  ADK's toolset owns the retry and there is no seam to make it configurable.
- **A tripped breaker produces a partial report marked incomplete**, on the path
  refusals already take: recorded, reported as an account cut short, and never
  readable as a signal that came back clean.
- **The consultation bound moves out of the adapter.** `MAX_CONSULTATIONS` lives
  in `adapters/adk/consultation.py` and the Diagnostician's instruction imports
  it, which after slice 10 is the only import `adapters/crew/` makes from
  `adapters/adk/`. The default moves beside the setting in
  `configuration/settings.py`, and the instruction becomes a function of the
  budget it is told. `crew` may not import `adk` becomes a contract in
  `.importlinter`.

Out of scope: tuning any default against evidence (that is the evaluation
harness's job, and this slice is what gives it numbers to tune); whether the
two per-agent bounds should stay separate keys once the harness can say.

## Capabilities

### New Capabilities

None. Every bound here is a requirement on investigation or on config, both of
which already have specs.

### Modified Capabilities

- `investigation`: the consultation bound becomes operator-configurable and is
  restated in terms of hops; a specialist's own tool calls gain a bound; an
  investigation gains a wall-clock bound; a breaker that trips is reported as an
  incomplete investigation rather than a failed one.
- `config`: `max_agent_hops` changes meaning and default, `max_mcp_retries` is
  removed and refused by name, and the remaining breakers gain the requirement
  that each is read by what it bounds.
- `project-conventions`: `crew` may not import `adk`, enforced as an
  import-linter contract shown red before it is trusted green.

## Impact

- `configuration/settings.py` — `CircuitBreakers` loses a field, changes a
  default, and gains the documented defaults as `ClassVar`s per the convention
  the other sections follow.
- `configuration/adapters/yaml/loader.py` — no schema wiring changes; the
  removed key is refused by the existing unknown-key path.
- `investigation/adapters/adk/consultation.py` — `MAX_CONSULTATIONS` leaves;
  the budget and the deadline are supplied per investigation.
- `investigation/adapters/adk/evidence.py` — `log_tool_call` gains the
  per-specialist bound it was left as a seat for.
- `investigation/adapters/adk/agent.py` — connection timeouts come from
  configuration; `build_agent` and `build_manager` are told their bounds.
- `investigation/adapters/adk/investigator.py` — owns the deadline and the
  wall-clock backstop.
- `investigation/adapters/crew/reasoners/diagnostician.py` — the instruction
  becomes a function of the budget, dropping its import of `adk`.
- `app/composition.py` — passes `CircuitBreakers` into the investigator.
- `.importlinter` — one new forbidden contract.
- `config.yaml`, `docs/vision.md`, `docs/adapters.md`, `README.md` — the
  breakers as they now are.
