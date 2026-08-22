Each numbered task is one red/green/refactor cycle unless it says otherwise:
write the failing test named in it, watch it fail, make it pass, clean up. The
four CI commands from `AGENTS.md` must pass before any group is called done.

The order is chosen so the suite stays green throughout: the new path is built
beside the old one, the logs specialist moves onto it, and only then is the
port deleted. See `design.md` — Migration Plan.

## 1. Domain: evidence that is not a log line

- [x] 1.1 `EvidenceItem` (id, instant, summary, payload) rejecting an item with
      no summary — test it keeps what a human needs to recognise evidence from
      any tool, and that the raw payload travels with it
- [x] 1.2 Point `Finding.examples` at `EvidenceItem` — test a finding built
      from items still caps at `MAX_EXAMPLES_PER_FINDING` and still refuses to
      claim more occurrences than it shows
- [x] 1.3 `Findings.retrieval_failures`, defaulting to empty, with a `complete`
      reading — test that empty means complete, that failures make it
      incomplete, and that incompleteness is independent of whether anything
      notable was found
- [x] 1.4 Confirm `tests/unit/test_architecture.py` still passes: the domain
      imports the standard library and nothing else

## 2. The shallow normaliser

- [x] 2.1 Items from a result that is a bare list — test each entry becomes one
      `EvidenceItem` in order
- [x] 2.2 Items from a result wrapping its entries in a recognised envelope key
      — test the entries are found and the envelope is not itself an item
- [x] 2.3 A result with no readable items — test it yields no items rather than
      an error, so a tool the project has never seen degrades to a citable
      aggregate
- [x] 2.4 Normalising one item: an instant read where the payload offers one and
      absent where it does not, a summary derived from the payload, and the
      payload retained verbatim — test all four, including a payload with no
      recognisable timestamp

## 3. Call-and-item citations

- [x] 3.1 `Retrieved` retains a tool result under `call-N` — test two calls in
      one investigation get distinct identifiers and the results are kept
      verbatim
- [x] 3.2 Items within a retained call are addressable as `call-N/item-M` —
      test the identifiers the model is shown are the ones that resolve
- [x] 3.3 Resolving a call-level citation yields the call's evidence — test a
      finding about an aggregate keeps its evidence
- [x] 3.4 Resolving an item-level citation yields that item — test a pattern
      finding keeps exactly the items it cited
- [x] 3.5 A citation naming a call or item never retrieved resolves to nothing
      and the finding is discarded with the discard logged — test an invented
      citation, a mixture of real and invented, and a finding citing neither
      grain
- [x] 3.6 Test a fresh `Retrieved` per investigation: an identifier from an
      earlier investigation resolves to nothing

## 4. The gate: a failed retrieval is not silence

- [x] 4.1 The evidence callback retains a successful result and hands the model
      the citable form instead of the raw one — test the model never sees the
      raw payload and always sees the identifiers
- [x] 4.2 A result carrying `isError` is recorded as a retrieval failure and
      replaced with an explicit refusal — test the replacement states the
      retrieval failed, that it cannot be read as an empty result, and that the
      failed call is not citable as evidence
- [x] 4.3 A result carrying an `error` key is treated identically — test ADK's
      converted-exception shape takes the same path as a server-side error
- [x] 4.4 A result that cannot be read at all is a retrieval failure, not an
      empty one — test an unreadable payload is recorded and refused rather
      than passed through as nothing found
- [x] 4.5 Failures accumulate on the investigation alongside successful
      evidence — test two failures and three successes are all recorded, and
      the successes stay citable
- [x] 4.6 `before_tool_callback` is registered and logs the call without
      refusing it — test it is reached and changes nothing, so slice 12 has a
      seat with a test already on it

## 5. The specialist declaration

- [x] 5.1 The declaration value (name, signal, instruction, output schema,
      toolsets with their permitted tool names, optional model) — test a
      declaration missing its instruction or its signal is rejected
- [x] 5.2 Build an agent from a declaration — test the agent's name,
      instruction, and output schema come from the declaration and nothing
      else does
- [x] 5.3 The toolset built for a declaration is filtered to the tool names it
      named — test a tool the declaration did not name is not exposed, and
      that the endpoint asks for the declared toolsets
- [x] 5.4 A declaration naming its own model beats the default; one naming none
      takes the default — test both against a crew of two declarations
- [x] 5.5 Deployment facts are supplied, not declared — test the same
      declaration built against two different endpoints and credentials is
      unchanged
- [x] 5.6 The connection params carry explicit connect and read bounds — test
      they are set rather than left to the framework's defaults
      (`design.md` — the two MCP circuit breakers)

## 6. The logs specialist as the first declaration

- [x] 6.1 Rewrite the logs instruction: the platform's log tools and query
      dialect, cite `call-N/item-M` for a pattern and `call-N` for an
      aggregate, and never conclude anything about a service from a retrieval
      that reported failure — test the instruction asks for each, without
      constructing an agent
- [x] 6.2 The logs declaration names its signal, its toolset, and its log tools
      — test the crew contains it and that it reaches no tool outside its
      declaration
- [x] 6.3 The output schema cites at both grains — test a payload citing a call,
      one citing items, and one citing both all build findings

## 7. The investigator drives declarations

- [x] 7.1 The coordinator runs every declaration in the crew and concatenates
      the findings, each naming its own signal — test with two stub
      declarations that the caller sees one result of unchanged shape
- [x] 7.2 Some retrievals failed, findings produced → findings returned marked
      incomplete — test against a stub model
- [x] 7.3 Every retrieval failed → `InvestigatorError`, not an empty result —
      test this is the outcome even when the stub model reports findings
      confidently
- [x] 7.4 No retrieval attempted → an ordinary complete result — test a model
      that chose not to look is not a failure
- [x] 7.5 A specialist that errors outright is still a failed investigation —
      test the existing failure path survives the restructure
- [ ] 7.6 Confirm the retry arc is untouched: a failed investigation still
      spends one attempt and is retried on the next run

## 8. The report

- [x] 8.1 Render `EvidenceItem` in the investigated report — test the body
      carries each finding's summary lines and instants
- [x] 8.2 An incomplete investigation says so — test the body states the
      evidence gathered was incomplete, alongside the findings it did produce
- [x] 8.3 A complete investigation carries no such note — test both the
      notable and the nothing-notable cases
- [x] 8.4 Test the incompleteness note is independent of the "investigation
      could not complete" report, which still covers the spent-attempts case

## 9. Per-specialist model configuration

- [x] 9.1 `investigation.specialists.<name>.model` in the config port and the
      YAML loader — test a specialist named there runs on that model and every
      other on `investigation.model`
- [x] 9.2 Test the section is optional and an unknown specialist name is
      refused by name, like any key the schema has never heard of
- [x] 9.3 Test the environment override path reaches a per-specialist model
      like every other behavior value

## 10. Composition and removal

- [x] 10.1 The composition root builds the crew from the declarations and
      supplies endpoint, headers, and default model — test it names no tool
- [x] 10.2 Delete `ports/observability_platform.py`, `DatadogMcpPlatform` and
      its translation, the `search_logs` tool wrapper, and `LogRecord` —
      confirm nothing imports them and the whole suite is green
- [x] 10.3 Confirm `tests/unit/test_architecture.py` passes: `mcp` is no longer
      imported by our adapter directly, and `google`, `mcp`, and `pydantic`
      remain forbidden in the domain and the ports

## 11. Integration and the live run

- [x] 11.1 A fake in-process MCP server the toolset connects to — test the
      toolset build, the tool filter, and the callback over a real ADK tool
      path with no network and no model
- [x] 11.2 Test a failing tool on that fake server produces a retrieval failure
      and a refusal through the real ADK path, not only through the unit-level
      callback
- [x] 11.3 Confirm the end-to-end run still passes with its fake investigator
      and no new dependency
- [x] 11.4 A credential-gated live run against the real Datadog MCP server and
      a real model, skipped without credentials, following
      `test_datadog_alert_source_live.py` — it proves the declared tool names
      exist, the filter admits them, and a model calls them

## 12. Documentation

- [ ] 12.1 Record the MCP circuit-breaker decision in `docs/vision.md`'s
      circuit-breaker section: `mcp_call_timeout_seconds` re-expressed through
      the connection params, `max_mcp_retries` superseded, both wired in slice
      12
- [ ] 12.2 Rewrite the README's extension guide: a notification channel is a
      port to implement, observability tooling is a specialist to declare, one
      specialist is a complete contribution, and nothing checks whether an
      instruction is good — that is slice 8
- [ ] 12.3 Update the README's architecture diagram via the mermaid MCP tool so
      the investigation path shows the filtered toolset and the evidence
      callback rather than the retired port
- [ ] 12.4 Note in the README that a run's model and tool spend rises with a
      specialist's tool count, and stays bounded only by the cooldown until
      slice 12
