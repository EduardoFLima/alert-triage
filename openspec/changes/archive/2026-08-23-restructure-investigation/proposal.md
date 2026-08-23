## Why

Slice 6 shipped the `ObservabilityPlatform` port and, in shipping it, showed
it should not be extended: the reasoning is in [Evidence and the platform
boundary](../../../docs/vision.md#evidence-and-the-platform-boundary). Every
later investigation slice — the evaluation harness, the three remaining
specialists, the Diagnostician — is built on whatever this boundary is, so
moving it now costs one adapter and moving it later costs four specialists
and their instructions.

This is slice 7 of the capability slice order in `docs/vision.md`, ordered
first among the investigation slices for exactly that reason.

## What Changes

- **BREAKING: the `ObservabilityPlatform` port is retired.** A specialist
  reaches the platform's MCP toolset directly, filtered to the tools that
  specialist is allowed. MCP is the boundary; the hand-written abstraction
  over it bought a neutrality that did not survive contact with a second
  vendor.
- **A specialist becomes a declaration** — its name, the signal it reports
  under, its instruction, its output schema, the toolsets and tool names it
  may reach, and optionally the model it runs on. The coordinator that runs
  the crew learns no tool signature, so slice 9 adds specialists by adding
  declarations.
- **A specialist may name its own model**, overridable per specialist under
  `investigation.specialists.<name>.model` without a schema rewrite.
- **The evidence check moves into `after_tool_callback`**, which sees every
  tool result before the model does. Catching fabrication there is strictly
  more general than catching it in an adapter method, because it covers tools
  nobody wrote a method for.
- **Citations generalise to call-and-item** (`call-3`, `call-3/item-7`). A
  pattern finding cites items; an aggregate finding — a flame graph, a
  dependency map, a waterfall — cites the call. A finding citing neither is
  still discarded.
- **A failed retrieval can no longer read as silence.** This is the gate on
  the slice. With a toolset, a failure comes back as a result the *model*
  interprets, and it may well decide the service was quiet — the opposite
  finding. A failed call is replaced with a refusal the model cannot misread,
  and recorded, so an investigation that could not see everything is reported
  as incomplete rather than as clean.
- **One shallow normaliser replaces the per-tool domain type.** Every
  retrieved item gets an id, an instant, and a human-readable summary
  alongside its raw payload, so evidence still renders in an email without a
  `LogRecord` equivalent per tool. **BREAKING** for `LogRecord`, which the
  generalised evidence value replaces.
- **The Logs specialist is rewritten as the first declaration**, naming
  Datadog's log tools and Datadog's query dialect in its instruction, because
  query dialects are not translatable and the old port only pretended
  otherwise.
- **The two MCP-level circuit breakers are decided, not enforced.** ADK owns
  the MCP client now, so `mcp_call_timeout_seconds` is re-expressed through
  its connection parameters and `max_mcp_retries` is superseded by the retry
  ADK already performs. Wiring both to config is slice 12's work, as are the
  per-agent, per-hop, and per-investigation bounds; this change records the
  decision and sets the connection bounds explicitly so ADK's defaults do not
  apply by accident.

Out of scope: the evaluation harness (slice 8), the remaining specialists
(slice 9), the Diagnostician (slice 10), escalating an incomplete
investigation (needs slice 11), enforcing any circuit breaker (slice 12).

## Capabilities

### New Capabilities

None. This change replaces how an existing capability is realised.

### Modified Capabilities

- `investigation`: the requirement that evidence is gathered through a
  project-vocabulary platform boundary is removed and replaced by one placing
  the boundary at MCP with a per-specialist tool filter. The evidence
  requirement generalises from log records to any retrieved item, and from
  record ids to call-and-item citations. New requirements cover a failed
  retrieval never reading as an absence of evidence, an investigation
  reporting itself as incomplete when part of its evidence could not be
  gathered, and a specialist being a declaration that owns its tools,
  instruction, schema, and model.
- `triage-run`: the report a run sends states when evidence gathering was
  partial, so "we looked and it was clean" and "we could not see all of it"
  are not the same message.
- `project-conventions`: the README's extension guide changes contract. A
  contributor plugging in their own observability tooling copies a specialist
  and swaps its tool names and instruction, rather than implementing a port —
  a contributor story rather than a migration story.

## Impact

- **Removed**: `ports/observability_platform.py`;
  `adapters/datadog/datadog_mcp.py`'s port implementation and its ~245 lines
  of JSON-to-JSON translation; `domain/findings.py`'s `LogRecord`.
- **New**: a specialist declaration type and a registry of declarations; the
  evidence callback pair (`after_tool_callback` for the check and the failure
  record, `before_tool_callback` as the seat slice 12 fills); the shallow
  evidence normaliser; a generalised evidence value in `domain/findings.py`.
- **Changed**: `adapters/adk/investigator.py` (drives declarations rather
  than one hard-wired agent), `adapters/adk/logs_agent.py` (becomes a
  declaration), `adapters/adk/evidence.py` (call-and-item citations),
  `adapters/datadog/` (endpoint and headers for the toolset, no port),
  `domain/report.py` (renders normalised evidence, states incompleteness),
  `ports/config.py` and the YAML loader (per-specialist model),
  `app/composition.py` (supplies deployment facts to declarations).
- **Dependencies**: none added. `mcp` stops being imported directly by our
  adapter and is reached through `google-adk`; both stay in the
  `forbidden_modules` contract in `pyproject.toml`.
- **Docs**: `docs/vision.md`'s circuit-breaker section records the MCP-bound
  decision; the README's extension guide is rewritten.
- **Cost and latency**: a specialist with a filtered toolset can make several
  tool calls where it previously made one, and no bound is enforced until
  slice 12. The cooldown remains the only bound on how often an investigation
  happens at all.
