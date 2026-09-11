## 1. The breaker schema

- [x] 1.1 Failing test: every `CircuitBreakers` default is stated as a
      `ClassVar` beside its field, the way `Grouping`, `Ingestion`, `ReNotify`,
      `Ledger` and `Investigation` state theirs
- [x] 1.2 Restate the four defaults as `ClassVar`s and have the fields default
      from them
- [x] 1.3 Failing test: `max_agent_hops` defaults to 8, and that default exceeds
      the number of specialists `CREW` declares
- [x] 1.4 Change the default from 2 to 8
- [x] 1.5 Failing test: `max_mcp_retries` is not a field of `CircuitBreakers`,
      and `config.yaml` declaring `circuit_breakers.max_mcp_retries` is refused
      at startup with the key named
- [x] 1.6 Remove the field; confirm the refusal comes from the existing
      unknown-key path and needs no new wiring
- [x] 1.7 Failing test: `CIRCUIT_BREAKERS_MAX_MCP_RETRIES` in the environment
      resolves nothing and changes no behavior
- [x] 1.8 Update the existing config tests that assert the old default and the
      removed key (`tests/unit/configuration/test_settings.py`,
      `tests/integration/configuration/test_yaml_config_loader.py`,
      `test_investigation_config.py`, `test_example_configuration.py`)

## 2. The budget leaves the adapter

- [x] 2.1 Failing test: the Diagnostician's instruction states the budget it is
      given, so two different budgets produce two different instructions
- [x] 2.2 Turn `DIAGNOSTICIAN_INSTRUCTION` into `diagnostician_instruction(hops)`
      and `DIAGNOSTICIAN` into `diagnostician(hops)` returning a `Reasoner`
- [x] 2.3 Delete `MAX_CONSULTATIONS` from `adapters/adk/consultation.py`; the
      default now lives in `CircuitBreakers`
- [x] 2.4 Update `build_manager` to build the Diagnostician from the configured
      budget

## 3. The crew does not import the framework

- [x] 3.1 Add the `crew` → `adk` forbidden contract to `.importlinter` and watch
      it fail on the real import that section 2 removes — confirm the failure
      names the offending module and import
- [x] 3.2 Add the contract's name to the list
      `tests/unit/test_architecture.py` asserts is present, so the rule going
      missing fails a build
- [x] 3.3 Confirm green once the import is gone, then re-confirm red against a
      deliberate `crew` → `adk` import and remove it

## 4. A hop is a consultation

- [x] 4.1 Failing test: an investigation configured with a hop bound refuses
      consultations beyond it, records the refusals, and still concludes on what
      it gathered
- [x] 4.2 Failing test: an unconfigured investigation is bounded by the
      documented default rather than unbounded
- [x] 4.3 Failing test: the budget stated in the manager's instruction is the
      configured number, not a different one
- [x] 4.4 Have `Consulted` take its bound rather than read a module constant,
      and `build_manager` supply the configured value to both the instruction
      and the callback from one place
- [x] 4.5 Confirm the existing refusal wording and recording are unchanged — the
      bound became configurable, the refusal did not change

## 5. A specialist's own tool calls are bounded

- [x] 5.1 Failing test: a specialist making calls past its bound has the further
      calls declined, and reports on what it gathered before them
- [x] 5.2 Failing test: what a declined specialist is handed states the call did
      not happen and cannot be read as a platform that returned nothing
- [x] 5.3 Failing test: the count is cumulative across two consultations of the
      same specialist in one investigation
- [x] 5.4 Failing test: one specialist reaching its bound leaves every other
      specialist its full number of calls
- [x] 5.5 Add the per-investigation record of calls spent per specialist,
      alongside `Retrieved` and `Consulted`
- [x] 5.6 Give `log_tool_call` its body: decline past the bound, in the register
      `RETRIEVAL_FAILED` and `CONSULTATION_REFUSED` already use
- [x] 5.7 Failing test: a declined call reaches `Findings.retrieval_failures`,
      so the investigation is reported incomplete

## 6. An investigation is bounded in time

- [x] 6.1 Failing test: once the deadline has passed, the manager's next
      consultation is declined and the reasoning concludes on what it holds
- [x] 6.2 Failing test: once the deadline has passed, a specialist's next tool
      call is declined
- [x] 6.3 Failing test: what either declines states the call did not happen and
      cannot be read as an empty signal
- [x] 6.4 Add the deadline, computed from an injected monotonic clock, and check
      it in both `before_tool_callback` seats
- [x] 6.5 Failing test: a run that does not return is stopped, and the findings
      gathered before it was stopped survive
- [x] 6.6 Wrap the manager's run in `asyncio.timeout` inside `run_with_adk`,
      keeping `Consulted` and `Retrieved` owned by the investigator so
      cancellation destroys neither
- [x] 6.7 Failing test: an investigation completing inside its bound declines
      nothing and carries no incompleteness from time

## 7. What a trip is reported as

- [x] 7.1 Failing test: a trip with findings in hand returns them marked
      incomplete, delivers the report, and spends no attempt
- [x] 7.2 Failing test: the report states which bound was reached, not merely
      that the investigation was incomplete
- [x] 7.3 Failing test: a trip with no findings at all raises rather than
      reporting, so the incident is investigated again while attempts remain
- [x] 7.4 Failing test: that outcome stays distinct from a manager that *chose*
      to consult nobody, which is still an ordinary result
- [x] 7.5 Failing test: the incident keeps its alerts and its identity through
      any trip
- [x] 7.6 Implement the exits in `AdkInvestigator.investigate`

## 8. The platform call timeout

- [x] 8.1 Failing test: `connection_for` sets both `timeout` and
      `sse_read_timeout` from the configured `mcp_call_timeout_seconds`
- [x] 8.2 Failing test: an unset value bounds a call by the documented default
      of thirty rather than by ADK's own defaults
- [x] 8.3 Failing test: changing it leaves ingestion's
      `request_timeout_seconds` unchanged, and the reverse
- [x] 8.4 Add `breakers: CircuitBreakers` to `Deployment`; read the timeout in
      `connection_for` and retire `CONNECT_TIMEOUT_SECONDS` /
      `READ_TIMEOUT_SECONDS`

## 9. Wiring

- [x] 9.1 Failing test: the investigator a run is handed enforces the
      deployment's configured breakers, not the defaults
- [x] 9.2 Pass `CircuitBreakers` through `build_investigator` into `Deployment`
      and `AdkInvestigator`
- [x] 9.3 Confirm the composition root is still the only place that names them

## 10. Documentation

- [x] 10.1 Rewrite `docs/vision.md`'s Circuit breakers section: the table's
      `max_agent_hops` default, the two per-agent paragraphs, the removal of
      `max_mcp_retries`, and the `mcp_call_timeout_seconds` wiring — and the
      Config file section's `circuit_breakers` entry
- [x] 10.2 Update the two places in `docs/vision.md` that route the reader to
      that section for what bounds the manager (the "Which specialists run"
      section and the `before_tool_callback` note)
- [x] 10.3 Update `config.yaml`'s commented `circuit_breakers` block: the new
      default, the new meanings, and the removed key
- [x] 10.4 Update `docs/adapters.md` where it says the breakers are not yet
      wired to configuration
- [x] 10.5 Update `README.md` if it states any breaker default

## 11. Before this is called done

- [x] 11.1 `uv run ruff check src tests`
- [x] 11.2 `uv run ruff format --check src tests`
- [x] 11.3 `uv run mypy`
- [x] 11.4 `uv run pytest`
- [x] 11.5 Live run against a real account, per
      [`docs/live-testing.md`](../../../docs/live-testing.md): this change edits
      the Diagnostician's instruction and the MCP connection parameters, neither
      of which a green local run establishes. Say plainly whether it was run
- [x] 11.6 Confirm no new file is read at runtime, so the `Dockerfile`'s
      copy-by-name list needs no entry
