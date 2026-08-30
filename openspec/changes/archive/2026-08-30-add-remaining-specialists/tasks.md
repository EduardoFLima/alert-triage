Red / green / refactor throughout, one cycle per behaviour. Every test below is
written failing and watched fail before the code that satisfies it exists.

## 1. The gate: an empty answer is not a failed retrieval

Done first because the infrastructure specialist cannot be trusted until it is,
and because a test that has never failed has not been shown to test anything.

- [x] 1.1 Write a failing unit test in
      `tests/unit/investigation/adapters/adk/` asserting that a tool result
      carrying an empty collection is retained as a retrieval that succeeded
      with no items, and records no failure.
- [x] 1.2 Write a failing unit test asserting the empty result does not mark the
      investigation incomplete — `Findings.complete` stays true.
- [x] 1.3 Watch both fail against today's `_failure_in`, which reads an empty
      answer as unreadable. Record what the failure says.
- [x] 1.4 Narrow `_failure_in` so only a result with nothing readable at all
      fails. Both tests green.
- [x] 1.5 Confirm the opposite direction still holds: the existing tests for a
      refused call, an error result, and an unreadable answer stay green. Add
      the missing case if `None` and `[]` are not both covered.

## 2. Signals

- [x] 2.1 Write a failing test for `Signal.APM`, `Signal.TRACE` and
      `Signal.INFRASTRUCTURE`, then add the three members to
      `investigation/contract.py`.

## 3. APM specialist

- [x] 3.1 Write failing unit tests in
      `tests/unit/investigation/adapters/datadog/` for the declaration: it
      reports under `Signal.APM`, names its two toolsets, permits exactly the
      four tools, and takes the deployment's model.
- [x] 3.2 Write failing unit tests for the instruction: it asks for latency,
      error rate and throughput; teaches the metric query dialect; asks for
      single-hop dependency evidence and forbids investigating the neighbour;
      asks about changes near the window without naming one as a cause; states
      both citation grains; bounds examples at `MAX_EXAMPLES_PER_FINDING`;
      forbids concluding from a failed retrieval; and forbids naming a root
      cause.
- [x] 3.3 Write a failing test asserting every tool the declaration permits is
      named in the instruction, and every tool the instruction names is
      permitted.
- [x] 3.4 Write the output schema and a failing test that it offers no field an
      agent could write evidence into.
- [x] 3.5 Create `specialists/apm.py` satisfying the above.

## 4. Trace specialist

- [x] 4.1 Failing declaration tests: reports under `Signal.TRACE`, one toolset,
      permits exactly its two tools, takes the deployment's model.
- [x] 4.2 Failing instruction tests: search spans before fetching a trace;
      report where time went or where the request broke; report only about
      retrieved requests and never a typical one; the citation, example-bound,
      failed-retrieval and no-root-cause rules as above.
- [x] 4.3 Failing tool/instruction agreement test and output schema test, as
      3.3 and 3.4.
- [x] 4.4 Create `specialists/trace.py`.

## 5. Infrastructure specialist

- [x] 5.1 Failing declaration tests: reports under `Signal.INFRASTRUCTURE`, two
      toolsets, permits exactly its four tools, takes the deployment's model.
- [x] 5.2 Failing instruction tests: asks for CPU, memory, disk and network;
      asks for workload state including restarts where the platform has one;
      **states that a platform answering "none" means the deployment does not
      have that signal and is not a failure to report or work around**; plus the
      citation, example-bound, failed-retrieval and no-root-cause rules.
- [x] 5.3 Failing tool/instruction agreement test and output schema test.
- [x] 5.4 Create `specialists/infrastructure.py`.

## 6. The crew

- [x] 6.1 Write a failing test that `CREW` contains all four specialists, still
      names each once, and that `crew_for` applies a configured model to any of
      them by name.
- [x] 6.2 Add the three declarations to `CREW`.
- [x] 6.3 Write a failing test that an investigation over a crew of four returns
      findings from each, each naming its own signal, with the result the same
      shape a single specialist's is. Drive it through `AdkInvestigator` with a
      stubbed `run_specialist`, no model and no network.
- [x] 6.4 Confirm nothing in `AdkInvestigator`, `Retrieved`, the port or the
      contract needed editing beyond the `Signal` members. If something did,
      stop and record why in design.md before continuing — that is slice 7's
      claim failing.

## 7. The report

- [x] 7.1 Write a failing test that a report for an investigation finding
      nothing notable names every signal examined rather than only the logs.
- [x] 7.2 Write a failing test that the wording widens by itself when a
      specialist joins the crew, rather than being a fixed list.
- [x] 7.3 Replace `NOTHING_NOTABLE` in `triage/domain/report.py` with wording
      derived from the crew's declared signals. Green.
- [x] 7.4 Check the existing report tests for others that assume one signal, and
      fix what has become untrue.

## 8. Configuration example

- [x] 8.1 Add `investigation` to `SECTIONS` in
      `tests/integration/configuration/test_example_configuration.py` and watch
      it fail — the example has no such section.
- [x] 8.2 Add the `investigation:` section to `config.example.yaml`: `model`,
      `max_attempts`, and a commented `specialists:` entry showing a
      per-specialist model override. Name the four specialists, since the
      example is the only place an operator learns what may be named.
- [x] 8.3 Green, and confirm `docs/configuration.md` does not now contradict the
      example.

## 9. Live confirmation (credential-gated)

- [x] 9.1 Rewrite `tests/integration/investigation/adapters/datadog/`'s live
      test to parameterise over `CREW` rather than naming the logs specialist,
      keeping the same two assertions: the declared tools exist and the filter
      admits them, and a real model given the instruction actually calls them.
- [x] 9.2 Confirm it still skips cleanly with no credentials.
- [x] 9.3 Run it against a real account. `core`, `kubernetes` and `logs`
      resolve and the filter admits every declared name; `apm` does not, for
      the Preview reason 9.4 records. Run repeatedly against `datadoghq.eu`.
      Tool-call counts were not recorded — see 9.5.
- [x] 9.4 `apm` is unreachable on this account: it is Preview and access was not
      granted. Both specialists now build from `APM_TOOLSET_AVAILABLE` in
      `specialists/preview.py`, which drives toolsets and instruction together so
      neither can claim a tool the other lacks. Deploy correlation survives on
      `core` through `search_datadog_events`; latency breakdown and Watchdog
      anomalies have no `core` substitute and leave the instruction. Recorded in
      design.md. Flipping the switch to `True` is the whole re-enablement.
- [x] 9.8 **Closed unmet.** Preview access is not coming in a timeframe worth
      holding this change open for. The four `apm` tool names have therefore
      never been confirmed against a real server, and the Preview branch of
      both declarations is unproven live — the unit tests assert its shape and
      nothing more. Re-enablement is still the one switch 9.4 describes, and
      flipping it should be followed by a live run before it is trusted.
- [x] 9.5 **Not doing.** `max_tool_calls_per_agent` has no body yet, so the
      counts would sit here unread until the slice that bounds tool calls
      needs them, by which time a fresh run is cheaper than a stale figure.
- [x] 9.6 Confirmed: `get_datadog_metric_context` and `search_datadog_events`
      both exist on the server and the filter admits them, established by the
      live per-toolset check. Both have since run and returned. The `apm`
      names remain unconfirmed — see 9.8.
- [x] 9.9 Fix what the first live run rejected. Three distinct 400s, all real:
      an incident of one alert spans an instant and no metric query accepts one
      (`query end is not after query start`); the model wrote log-query syntax
      into a metric scope (`'AND' and 'OR' cannot be mixed with ','`); and it
      asked a distribution metric for an aggregation nobody configured
      (`missing_aggregation :: AGG_AVG/AGG_P95`). The first was a production
      bug reaching every single-alert incident, fixed in the contract; the other
      two are instruction, now taught once in `specialists/dialect.py`.
- [x] 9.7 **Not doing.** Answering it properly means comparing what the
      specialists report with and without discovery over enough runs to see
      past the model's variance, which is a study rather than a task. The
      declaration keeps the discovery tool on the narrower ground that a
      specialist must be able to tell "not reported" from "healthy".

## 10. Before calling it done

- [x] 10.1 `uv run ruff check src tests`
- [x] 10.2 `uv run ruff format --check src tests`
- [x] 10.3 `uv run mypy`
- [x] 10.4 `uv run pytest`
- [x] 10.5 Confirm the architecture test still passes with no `.importlinter`
      edit — three specialist modules add no dependency and no context, so a
      contract change here would mean something is in the wrong place.
