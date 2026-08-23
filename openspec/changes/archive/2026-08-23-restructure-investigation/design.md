## Context

See `proposal.md` — Why, and `docs/vision.md` — "Evidence and the platform
boundary" for the argument this change carries out.

What exists: `ports/observability_platform.py` (one method, `search_logs`),
`adapters/datadog/datadog_mcp.py` (~245 lines implementing it over a raw MCP
client session), `adapters/adk/logs_agent.py` (one hard-wired `LlmAgent`),
`adapters/adk/evidence.py` (`Retrieved`, keyed `rec_N`, resolving into
`LogRecord`), `adapters/adk/investigator.py` (wraps the port method as an ADK
function tool), `domain/findings.py` (`Signal`, `LogRecord`, `Finding`,
`Findings`), `domain/report.py`, `app/composition.py`.

What stands and is not re-litigated here: the `Investigator` port and its
synchronous shape, the retry-across-runs arc and its ledger column, the
attempt bound, the run's stage ordering, `Signal`/`Finding`/`Findings` as
values, the delivery rules. Slice 6's design covers all of them.

Three constraints shape everything below.

- `AGENTS.md`: domain and ports import no vendor library, enforced by
  import-linter over the transitive graph. `google`, `mcp`, and `pydantic`
  are already forbidden there and stay forbidden.
- `docs/vision.md`: behavior in `config.yaml`, connections and credentials in
  the environment.
- TDD. Every decision below is chosen partly for whether it can be driven from
  a failing unit test with no model and no MCP server.

Verified against the installed ADK rather than assumed: `McpToolset` takes
`StreamableHTTPConnectionParams(url, headers, timeout, sse_read_timeout)` and
a `tool_filter` that is a list of tool names; `after_tool_callback` receives
`(tool, args, tool_context, tool_response)` and replaces the result by
returning a dict; `MCPTool.run_async` returns `CallToolResult.model_dump()`,
so a failure arrives as a dict carrying `isError`, or as `{"error": ...}`
when ADK's graceful handling converts an exception, and `retry_on_errors`
already retries once on a dead session.

## Goals / Non-Goals

**Goals:**

- Make widening what a specialist may ask a one-line edit to a declaration,
  so investigation quality can actually be iterated on.
- Keep the evidence discipline strictly stronger than slice 6's: it must now
  hold for tools nobody wrote a method for.
- Close the one genuine regression the port's removal opens — a failed search
  reading as a quiet service — and make that closure the gate on the slice.
- Keep a full run exercisable with no model, no MCP server, and no
  credentials, exactly as slice 6 did.

**Non-Goals:**

- Enforcing any circuit breaker (slice 12). This change *decides* the two
  MCP-level ones and leaves the seat for the per-agent one; it wires none of
  them to config.
- Adding specialists (slice 9) or judging instruction quality (slice 8).
- Making the pipeline async, or running specialists concurrently.

## Decisions

### The specialist declaration

A frozen dataclass in the ADK adapter, holding everything that makes a
specialist itself: `name`, `signal`, `instruction`, `output_schema`,
`toolsets` (a toolset name and the tool names allowed within it), and
`model: str | None`. A module-level tuple of declarations is the crew. The
coordinator takes a declaration plus deployment facts — endpoint, headers,
default model — and builds an `LlmAgent`; it never names a tool.

*Alternative — a `Specialist` protocol each agent implements.* Rejected: a
declaration is data, so the crew can be asserted in a unit test by reading it,
and a contributor adds one by copying a tuple rather than by satisfying an
interface. The vision's contributor story is the whole point, and a protocol
prices it back up.

`model: str | None` is what makes per-specialist models cheap: `None` means
the default from `investigation.model`, and
`investigation.specialists.<name>.model` overrides it. The config schema
grows one open mapping keyed by specialist name rather than one field per
specialist, so slice 9 adds declarations without touching the loader.

### Tools come from a filtered `McpToolset`, not from wrapped port methods

Each declaration names a toolset and the tool names within it. The
coordinator builds one `McpToolset` per entry with
`StreamableHTTPConnectionParams` pointed at
`https://mcp.<DD_SITE>/v1/mcp?toolsets=<names>` and `tool_filter` set to the
tool names. The filter is belt and braces with the endpoint's `toolsets`
query parameter: the endpoint bounds what the server offers, the filter
bounds what ADK exposes, and only the second is under our control if the
server's toolset grouping changes.

The model now discovers tools at runtime — signatures, parameters, and the
platform's query dialect come from the server rather than from us. That is
the capability the port was trading away, and buying it back is the change.

*Alternative — keep the port and add fourteen more methods.* Rejected, at
length, in `docs/vision.md`. Not revisited here.

### Citations become call-and-item

`Retrieved` stops being a log-record registry and becomes a record of tool
calls. Every result passing `after_tool_callback` is retained verbatim under
`call-N`; every discrete item found within it is retained under
`call-N/item-M`. Both are handed to the model in place of the raw result, so
what the model reads is what it may cite.

Finding what the "items" are is the one shallow normaliser, and it is
deliberately shallow: if the result carries a list under a recognised
envelope key, or is a list, those are the items; otherwise the call has no
items and can only be cited whole. No per-tool knowledge, and a tool the
project has never seen degrades to a citable aggregate rather than to an
error.

Each item is normalised to an id, an instant where one can be read, a
human-readable summary, and the raw payload. `LogRecord` is replaced by this
`EvidenceItem` in the domain — one type for all tools, which is what stops
slice 9 from adding four more.

*Alternative — keep `LogRecord` and add a type per signal.* Rejected: it
reintroduces the port's economics one layer down. The report needs a line of
text and a timestamp to render evidence; anything richer is per-tool work,
and the raw payload travels alongside for anyone who wants it.

*Alternative — items only, no call-level citation.* Rejected: it is what
slice 6 had, and it silently excludes flame graphs, dependency maps, and
waterfalls — several of the most useful tools available.

### The evidence check and the failure record live in `after_tool_callback`

One callback, registered on every specialist, closing over this
investigation's `Retrieved`. It does three things in order: detect a failed
result, retain a successful one, and replace what the model sees.

Failure detection is `isError` truthy, or an `error` key, or a payload that
cannot be read at all. A failed call is **not** retained as evidence; it is
recorded as a retrieval failure and replaced with an explicit refusal — a
result whose content states that the retrieval failed and that no conclusion
about the service may be drawn from it. This is the slice's gate: the model
must be unable to read the failure as silence, and it is a unit test, not a
hope.

The callback is registered per agent rather than as an ADK plugin. A plugin
is global to the runner and would have to find its way to the right
investigation's `Retrieved`; a closure already has it, and a fresh one per
investigation is what scopes citations to this incident — the property slice
6 relied on and this change keeps.

`before_tool_callback` is registered too, as a pass-through that logs the
call. It exists so slice 12 has a seat and a test already reaching it; it
enforces nothing.

### `Findings` gains incompleteness, not a second failure mode

`Findings` grows `retrieval_failures: tuple[str, ...]` — empty means
everything asked for was gathered. The report renders a note when it is not
empty. The domain reads it as one boolean question, `complete`.

The interesting case is the boundary with failure, and getting it backwards
is the expensive mistake. Three outcomes, and only three:

| Retrievals | Findings | Outcome |
|---|---|---|
| some succeeded | any | `Findings`, marked incomplete if any failed |
| all failed | any | `InvestigatorError` |
| none attempted | any | `Findings` — the model chose not to look |

The middle row is why the callback records failures rather than only
replacing them. A model told "the retrieval failed" may still write a
plausible finding out of nothing; if every retrieval failed, there is no
evidence for any citation to resolve against, so the findings would drop
anyway — but they would drop into an empty "nothing notable", which is
exactly the misreading this slice exists to prevent. Raising instead keeps
the retry arc intact: the incident is retried on the next run, as it was
before this change.

*Alternative — an `incomplete` boolean.* Rejected: the failures are what
someone tuning the investigation needs to read, and a boolean derived from a
tuple costs nothing while the reverse loses the reasons.

### The logs specialist is rewritten, not ported

Its instruction now names Datadog's log tools and Datadog's query syntax,
because the model composes the query and the dialect is not translatable. It
also gains the two rules the new citation scheme needs: cite `call-N/item-M`
for a pattern and `call-N` for an aggregate, and never conclude anything
about a service from a retrieval that reported failure.

Its declaration names the `core` toolset and the log tools within it. The
instruction stays a module constant so a unit test asserts what it asks for
without constructing an agent — the discipline slice 6 established and
`project-conventions` requires.

### The two MCP circuit breakers, decided

ADK owns the MCP client, so neither of the vision's MCP-level breakers can be
enforced by us as written:

- `mcp_call_timeout_seconds` is re-expressed as
  `StreamableHTTPConnectionParams.timeout` and `sse_read_timeout`. This
  change sets both to explicit constants beside the connection params, so
  ADK's defaults (5s connect, 300s read) do not apply by accident to a
  30-second intent. Reading them from config is slice 12's wiring.
- `max_mcp_retries` is **superseded**. ADK's `retry_on_errors` already
  rebuilds a dead session and retries once, and there is no seam to make that
  count configurable without reimplementing the toolset. Slice 12 removes the
  key rather than leaving an operator setting that does nothing.

Recorded in `docs/vision.md`'s circuit-breaker section, since that document
explicitly left the decision to this change. The `CircuitBreakers` config
values stay as they are and stay unread — half-enforcing a bound reads as
done, which is worse than not enforcing it.

### Removals

`ports/observability_platform.py` goes, and with it
`ObservabilityPlatformError`, `DatadogMcpPlatform`, `records_from`, and the
`search_logs` tool wrapper in the investigator. What survives from
`datadog_mcp.py` is the endpoint and header derivation, which the toolset
needs; the envelope-reading logic moves into the normaliser, where it becomes
tool-agnostic. `LogRecord` goes, replaced by `EvidenceItem`.

`AdkInvestigator` no longer catches `ObservabilityPlatformError` — nothing
raises it. It catches the retrieval-failure record instead, per the table
above.

### Testing

- `tests/unit/` — the callback against canned tool results: a success is
  retained and re-presented with citable ids; a result with `isError` is
  recorded as a failure and replaced with a refusal, and is *not* citable; a
  result with an `error` key likewise; a result with no readable items is
  citable whole and not by item. The normaliser against a list, an envelope,
  a bare aggregate, and a payload with no timestamp. Citation resolution at
  both grains, including a call-level cite, an invented one, and a mixture.
  The declaration-to-agent build, asserting the tool filter is what the
  declaration named and that a declaration's model beats the default. The
  three-row outcome table above, against a stub model. The report's
  incompleteness note.
- `tests/integration/` — the end-to-end run keeps its fake investigator. A
  fake MCP server (an in-process server the toolset connects to) exercises
  the toolset build, the filter, and the callback against a real ADK tool
  path with no network and no model.
- A credential-gated live run against the real Datadog MCP server and a real
  model, following `test_datadog_alert_source_live.py`'s skip pattern. It is
  the only thing that proves the tool names in the declaration exist, that
  the filter admits them, and that a model actually calls them — none of
  which a fake can establish. Slice 6 deliberately deferred this rather than
  write it against an architecture being replaced; there is no longer a
  reason to defer it.

## Risks / Trade-offs

- **The gate can regress silently.** A future edit that stops replacing a
  failed result reintroduces exactly the misreading this slice exists to
  prevent, and nothing about the output looks wrong. → It is a unit test on
  the callback and a scenario in the spec, and the "all retrievals failed"
  path raises rather than returning empty, so the failure mode has two
  independent guards.
- **Runtime tool discovery means less predictable spend.** A specialist with
  six tools will call more of them than one with a single method, and no
  per-agent bound is enforced until slice 12. → The cooldown still bounds how
  often an investigation happens; `before_tool_callback` is registered and
  tested now so slice 12 is a body, not a boundary. Worth landing slice 12
  close behind.
- **The instruction now carries platform-specific query syntax**, so a model
  that composes a bad query fails in a way no type checker sees. → The
  failure surfaces as a retrieval failure rather than as silence, which is
  the whole point of the gate; the live run is what catches a wrong tool
  name, and slice 8's harness is what catches a bad instruction.
- **`EvidenceItem` is shallower than `LogRecord` was.** A report renders a
  summary line rather than a structured log line, so evidence reads slightly
  worse for logs specifically. → The raw payload travels with it, and one
  normaliser for fifteen tools is the trade the vision makes explicitly.
- **A large blast radius for one slice.** A port, an adapter, a domain type,
  the report, the config schema, and the README all move together. → They
  cannot move separately: the port's removal is what forces every one of
  them. The task order below keeps the suite green at each step by building
  the new path before deleting the old.
- **The live test costs money and can fail for reasons unrelated to the
  code.** → Credential-gated and skipped by default, exactly as the existing
  live tests are; it is never part of the fast loop.

## Migration Plan

No data migration. The ledger schema is untouched, `Findings` gains a field
with an empty default, and a ledger file written before this change opens
unchanged.

Operationally: a deployment that could investigate before can investigate
after. The endpoint and credentials are the same `DD_SITE` / `DD_API_KEY` /
`DD_APP_KEY` already required, and no new environment variable appears.
`config.yaml` files stay valid — `investigation.specialists` is optional and
absent means every specialist runs on the default model.

Order of work, so the suite stays green: build the declaration, the
normaliser, and the callback beside what exists; move the logs specialist onto
them; then delete the port, its adapter, and `LogRecord` in one step once
nothing imports them. Rollback before that step is reverting a commit; after
it, reverting the change.

## Open Questions

- What the recognised envelope keys should be for finding items in a result.
  The current three (`logs`, `data`, `results`) came from one tool; the live
  run and slice 8's fixtures will show what the rest of the catalogue uses. It
  is one tuple, and a tool whose envelope is unrecognised degrades to a
  call-level citation rather than to an error, so widening it later changes no
  spec and no task.
- Whether the logs specialist should be given more than the log tools now
  that adding one is a word in a tuple. Deliberately not answered here:
  slice 8 exists to answer it with evidence, and answering it by feel is what
  this restructure is meant to stop.
