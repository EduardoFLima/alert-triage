Each numbered task is one red/green/refactor cycle unless it says otherwise:
write the failing test named in it, watch it fail, make it pass, clean up. The
four CI commands from `AGENTS.md` must pass before any group is called done.

## 1. Domain: what an investigation comes back with

- [ ] 1.1 `Window` value (start, end) derived from an incident, rejecting an
      end before its start — test that an incident's window spans its earliest
      to its latest alert
- [ ] 1.2 `LogRecord` value (timestamp, level, message, service) — test it
      keeps what a human needs to recognise the evidence and nothing more
- [ ] 1.3 `Signal` enum with `LOGS`, and `Finding` (signal, observation,
      evidence) rejecting an observation with no evidence — test that a
      finding cannot claim something it cites nothing for
- [ ] 1.4 `Findings` holding a tuple of findings — test that empty findings
      are a valid, successful "nothing notable", distinct from any failure

## 2. Ports

- [ ] 2.1 `ports/observability_platform.py`: the
      `ObservabilityPlatform` protocol with `search_logs(service, window,
      query)` and `ObservabilityPlatformError` — test a substitute satisfies
      the protocol and that the error is defined beside the port
- [ ] 2.2 `ports/investigator.py`: the `Investigator` protocol with
      `investigate(incident) -> Findings` and `InvestigatorError` — test a
      substitute satisfies the protocol
- [ ] 2.3 Confirm `tests/unit/test_architecture.py` still passes: both ports
      import the domain and nothing else

## 3. Reporting findings

- [ ] 3.1 `build_investigated_report(incident, findings)` — test its subject
      names the service and its body carries every finding with its evidence
      and every alert with its time and link
- [ ] 3.2 Test the investigated report offers no hypothesis, root cause, or
      confidence level, and that findings with nothing notable read as such
      rather than as an empty section
- [ ] 3.3 Reword the pass-through report from "before investigation exists" to
      "investigation was attempted and did not complete" — test the body says
      so and no longer claims the alerts were never looked at

## 4. The run's investigation stage

- [ ] 4.1 Widen `ReportBuilder` to `Callable[[Incident, Findings | None],
      TriageReport]` and thread the investigator into `run` — test that a due
      incident is investigated and its report built from the findings
- [ ] 4.2 Test a suppressed report costs no investigation: the fake
      investigator is never called for an incident inside its cooldown
- [ ] 4.3 Add `Stage.INVESTIGATE` and catch `InvestigatorError` — test that a
      failed investigation still delivers the fallback report, still records
      the incident as reported, and yields a `RunFailure` naming the stage and
      the service
- [ ] 4.4 Test one group's investigation failure leaves the other groups their
      investigated reports, and the run finishes unsuccessfully

## 5. Config

- [ ] 5.1 `Investigation` section on the `Config` port with a `model` field
      and a documented default — test the default applies when the section is
      absent
- [ ] 5.2 YAML loader resolves `investigation.model`, with
      `INVESTIGATION_MODEL` overriding the file — test file-only,
      environment-only, and both-set
- [ ] 5.3 Test a credential-shaped key under `investigation` is inert:
      resolution proceeds as if it were absent

## 6. Datadog MCP adapter

- [ ] 6.1 Add `google-adk` to `dependencies` in `pyproject.toml`, confirm
      `google`, `mcp`, and `pydantic` are in the import contract's
      `forbidden_modules`, and run the architecture test
- [ ] 6.2 Derive the MCP endpoint from `DD_SITE` and build the auth headers
      from the existing `Connection` — test the URL for the default site and a
      non-default one, and that the header names are the ones the server
      expects
- [ ] 6.3 `search_logs` translating a canned MCP tool response into
      `LogRecord`s — test the mapping, an empty result, and a malformed
      payload raising `ObservabilityPlatformError`
- [ ] 6.4 Test a failed or refused MCP call raises
      `ObservabilityPlatformError` rather than returning an empty result

## 7. The Logs agent

- [ ] 7.1 The agent instruction as a module constant — test it asks for the
      incident's window, requires evidence for every observation, and forbids
      naming a root cause
- [ ] 7.2 The pydantic output schema and its translation into `Findings` —
      test a canned model payload maps to findings with `Signal.LOGS`, and
      that a payload with an evidence-free observation is rejected
- [ ] 7.3 Wrap the `ObservabilityPlatform` port's methods as ADK
      `FunctionTool`s — test the agent is given those tools and no
      platform-specific ones
- [ ] 7.4 The `Investigator` implementation: run the agent for one incident,
      `asyncio.run` at the adapter boundary, translate the result — test
      against a stubbed model, and test that a model or tool failure becomes
      `InvestigatorError`

## 8. Composition and the run end to end

- [ ] 8.1 Build the MCP platform and the ADK investigator in
      `app/composition.py` and inject them — test the run receives an
      investigator and that no adapter is named outside this module
- [ ] 8.2 Refuse to start when the model credential is absent, naming it —
      test nothing is fetched and the run finishes unsuccessfully
- [ ] 8.3 Extend `tests/integration/test_end_to_end.py` with a fake
      investigator: a complete run producing an investigated report, and one
      producing the degraded report after an investigation failure
- [ ] 8.4 Credential-gated live integration test against the real Datadog MCP
      server, following the pattern in `test_datadog_alert_source_live.py`

## 9. Documentation and close-out

- [ ] 9.1 README: the `investigation` config section, the model credential in
      the environment table, and a plain statement that a run now incurs model
      cost
- [ ] 9.2 README: update the architecture diagram via the mermaid MCP tool to
      show the Investigator and ObservabilityPlatform ports
- [ ] 9.3 Run all four CI commands clean, then answer the design's open
      questions from a real investigation: the default model, and whether
      evidence is structured records or prose
