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
      occurrences, examples) rejecting an observation with no examples — test
      that a finding cannot claim something it shows nothing for
- [ ] 1.4 Cap examples at `MAX_EXAMPLES_PER_FINDING` — test a finding built
      from many records keeps a bounded number of them while `occurrences`
      still reports the full count
- [ ] 1.5 `Findings` holding a tuple of findings — test that empty findings
      are a valid, successful "nothing notable", distinct from any failure
- [ ] 1.6 `Incident.investigation_attempts`, defaulting to 0, with
      `investigation_failed()` incrementing it and `findings_reported()`
      clearing it — test both transitions and that neither touches the
      incident's identity, alerts, or report stamp

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
      names the service and its body carries every finding with its occurrence
      count and its example records, and every alert with its time and link
- [ ] 3.2 Test the investigated report offers no hypothesis, root cause, or
      confidence level, and that findings with nothing notable read as such
      rather than as an empty section
- [ ] 3.3 Reword the pass-through report from "before investigation exists" to
      "investigation was attempted and did not complete" — test the body says
      so and no longer claims the alerts were never looked at
- [ ] 3.4 Test the two builders are chosen by the presence of findings alone,
      so report content stays independent of why the investigation failed

## 4. The retry decision

- [ ] 4.1 `TriageDecision` gains `should_investigate`: due to be reported and
      attempts remaining — test a due incident with none spent, a due incident
      with attempts spent, and a suppressed incident
- [ ] 4.2 Test that an incident whose report is overdue but whose attempts are
      spent is not investigated, however many runs handle it — the bound is on
      the incident, not on retries
- [ ] 4.3 Test a bound of one disables retrying, and a bound below one is
      rejected as unusable configuration
- [ ] 4.4 Test the counter clears on delivery, whatever the report carried, and
      that an incident whose alerts continue past the cooldown after such a
      report gets its full allowance back

## 5. Ledger persistence

- [ ] 5.1 Add `investigation_attempts` to the SQLite schema, defaulting to 0 —
      test the column is created and that a ledger file written before this
      change still opens
- [ ] 5.2 Record and retrieve the counter — test a round trip through a real
      file, and that a row written without the column reads back as zero
      attempts rather than failing
- [ ] 5.3 Test the counter survives a fresh process: an incident whose
      investigation failed is retrieved by a later run with the attempt spent

## 6. The run's investigation and retry stages

- [ ] 6.1 Widen `ReportBuilder` to take the incident and the findings or
      `None`; thread the investigator into `run` — test that a due incident is
      investigated and its report built from the findings
- [ ] 6.2 Test an incident inside its cooldown with a successful investigation
      behind it is never investigated: the fake investigator is not called
- [ ] 6.3 Add `Stage.INVESTIGATE` and catch `InvestigatorError` — test that a
      failed investigation delivers **nothing**, records the incident with the
      attempt spent and its report stamp untouched, and yields a `RunFailure`
      naming the stage and the service
- [ ] 6.4 Test a retry that fails again likewise delivers nothing, spends the
      second attempt, and still finishes the run unsuccessfully
- [ ] 6.5 Test a retry that succeeds delivers the findings, stamps the incident
      as reported, and clears the counter
- [ ] 6.6 Test a successful investigation whose delivery fails leaves the
      counter untouched, so the next run investigates again
- [ ] 6.7 Test an investigation that completes and finds nothing notable is
      still delivered, because it is a result rather than a failure
- [ ] 6.8 Test the last attempt failing delivers the alerts-only report, stamps
      the incident as reported, clears the counter, and still finishes the run
      unsuccessfully
- [ ] 6.9 Test an incident with attempts spent and no report delivered yet is
      not investigated again but is still delivered its alerts-only report, so
      a failed delivery is retried without spending an investigation
- [ ] 6.10 Test one group's investigation failure leaves the other groups their
      investigated reports, and the run finishes unsuccessfully

## 7. Config

- [ ] 7.1 `Investigation` section on the `Config` port with `model` and
      `max_attempts` fields and documented defaults — test both defaults apply
      when the section is absent
- [ ] 7.2 YAML loader resolves both keys, with `INVESTIGATION_MODEL` and
      `INVESTIGATION_MAX_ATTEMPTS` overriding the file — test file-only,
      environment-only, and both-set
- [ ] 7.3 Test a credential-shaped key under `investigation` is inert:
      resolution proceeds as if it were absent
- [ ] 7.4 Test `max_attempts` is resolved independently of the circuit
      breakers, and that changing one leaves the other alone

## 8. Datadog MCP adapter

- [ ] 8.1 Add `google-adk` to `dependencies` in `pyproject.toml`, confirm
      `google`, `mcp`, and `pydantic` are in the import contract's
      `forbidden_modules`, and run the architecture test
- [ ] 8.2 Derive the MCP endpoint from `DD_SITE` and build the auth headers
      from the existing `Connection` — test the URL for the default site and a
      non-default one, and that the header names are the ones the server
      expects
- [ ] 8.3 `search_logs` translating a canned MCP tool response into
      `LogRecord`s — test the mapping, an empty result, and a malformed
      payload raising `ObservabilityPlatformError`
- [ ] 8.4 Test a failed or refused MCP call raises
      `ObservabilityPlatformError` rather than returning an empty result

## 9. The Logs agent

- [ ] 9.1 The agent instruction as a module constant — test it asks for the
      incident's window, requires a citation for every observation, bounds the
      examples, and forbids naming a root cause
- [ ] 9.2 The pydantic output schema — test it offers the model no free-text
      evidence field, only citations, so invented log text has nowhere to go
- [ ] 9.3 Wrap the `ObservabilityPlatform` port's methods as ADK
      `FunctionTool`s — test the agent is given those tools and no
      platform-specific ones
- [ ] 9.4 The tool wrapper retains every returned record under an identifier it
      assigns — test two searches in one investigation both contribute, and
      that identifiers do not collide
- [ ] 9.5 Resolve citations into `Finding.examples` from the retained records —
      test a canned payload of resolvable citations produces findings whose
      examples are the real records, with `Signal.LOGS`
- [ ] 9.6 Drop what does not resolve — test a citation to a never-retrieved
      record drops that finding while its siblings survive, that the discard is
      logged with the offending citation, and that a payload of nothing but
      fabrications yields empty findings rather than an error
- [ ] 9.7 The `Investigator` implementation: run the agent for one incident,
      `asyncio.run` at the adapter boundary, translate the result — test
      against a stubbed model, and test that a model or tool failure becomes
      `InvestigatorError`

## 10. Composition and the run end to end

- [ ] 10.1 Build the MCP platform and the ADK investigator in
      `app/composition.py` and inject them — test the run receives an
      investigator and that no adapter is named outside this module
- [ ] 10.2 Refuse to start when the model credential is absent, naming it —
      test nothing is fetched and the run finishes unsuccessfully
- [ ] 10.3 Extend `tests/integration/test_end_to_end.py` with a fake
      investigator: a complete run producing an investigated report, and one
      delivering nothing after an investigation failure
- [ ] 10.4 Integration test of the retry arc across three runs against a real
      ledger file — fail, fail, succeed — asserting silence, silence, then one
      report carrying findings
- [ ] 10.5 Integration test of the arc that never succeeds — fail, fail, fail —
      asserting silence, silence, then the alerts-only report, and that a
      fourth run investigates nothing and delivers nothing
- [ ] 10.6 Credential-gated live integration test against the real Datadog MCP
      server, following the pattern in `test_datadog_alert_source_live.py`

## 11. Documentation and close-out

- [ ] 11.1 README: the `investigation` config section including
      `max_attempts`, the model credential in the environment table, and a
      plain statement that a run now incurs model cost
- [ ] 11.2 README: explain that a failed investigation is silent and retried,
      so an operator understands why a firing service can be quiet for a few
      runs and what the alerts-only report means when it does arrive
- [ ] 11.3 README: update the architecture diagram via the mermaid MCP tool to
      show the Investigator and ObservabilityPlatform ports
- [ ] 11.4 Run all four CI commands clean, then answer the design's open
      questions from a real investigation: the default model, and whether
      evidence is structured records or prose
