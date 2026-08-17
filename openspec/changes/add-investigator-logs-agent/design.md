## Context

See `proposal.md` — Why. The pipeline is complete and injectable: `app/run.py`
depends on `AlertSource`, `TriageLedger`, `Notifier`, and `Config`, takes its
`now` and its id generator as arguments, and receives a `ReportBuilder`
callable that turns an incident into a `TriageReport`. `app/composition.py` is
the only module that names an adapter. Every existing port is synchronous, for
the reason spelled out in `ports/alert_source.py`: nothing here has concurrency
to exploit, and a component that has none should not push an event loop into
the composition root.

Three constraints shape everything below.

- `AGENTS.md`: the domain and the ports import no vendor library, and this is
  enforced by import-linter contracts in `pyproject.toml` that walk the
  transitive import graph. `google`, `mcp`, and friends are already in the
  forbidden list, so the boundary bites from the first commit.
- `docs/vision.md`: behavior belongs in `config.yaml`, connections and
  credentials in the environment.
- TDD, red/green/refactor, one cycle per behavior. Every decision below is
  chosen partly for whether it can be driven from a failing unit test with no
  network and no model.

## Goals / Non-Goals

**Goals:**

- Establish the port shapes that slices 7 and 8 extend without reshaping:
  adding the APM, Trace, and Infrastructure agents must touch neither the run,
  nor the report, nor the `ObservabilityPlatform` port's design.
- Keep a full run exercisable with no network, no model, and no credentials.
- Make the Logs agent's own behavior — its instruction, its evidence
  discipline — testable separately from the machinery that runs it.

**Non-Goals:**

- Enforcing the circuit breakers. They are already in `Config` and stay
  unread; slice 10 owns them. A half-enforced bound is worse than an
  unenforced one, because it reads as done.
- Any cross-signal reasoning, hypothesis, or confidence (slice 8).
- Escalating an incomplete investigation (needs slice 9's escalation path).
- Evaluating agent output quality. Tests here assert the plumbing and the
  contract, not that a model reasons well.

## Decisions

### The `Investigator` port is synchronous and takes an incident

```
investigate(incident: Incident) -> Findings   # raises InvestigatorError
```

Synchronous, matching every other port. ADK is async underneath, so the
adapter owns an `asyncio.run` at its boundary and the composition root never
sees a loop.

*Alternative — an async port.* It would avoid a loop-per-investigation and
let slice 7's four specialists run concurrently for free. Rejected for now: it
would make `run`, `composition`, and `main` async for one adapter's benefit,
and slice 7 can parallelise *inside* the adapter, which is where the
concurrency actually lives. If a later slice needs the whole pipeline async,
that is its own change and its own justification.

Takes an `Incident`, not a group or a list of alerts: the incident already
carries the service, the alerts, and — through `started_at` and
`latest_alert_at` — the window. Nothing else needs to be passed, and nothing
needs to be recomputed.

### `Findings` is a domain value; the signal is an enum

```
Signal        StrEnum: LOGS today; APM, TRACE, INFRASTRUCTURE in slice 7
Finding       signal, observation, evidence
Findings      findings: tuple[Finding, ...]
```

`Findings` with an empty tuple *is* "queried successfully, nothing notable" —
a legitimate success the spec requires be distinguishable from failure.
Failure is `InvestigatorError`, so the two cannot be confused by construction
and no `succeeded` flag has to be kept honest.

There is deliberately no place for a hypothesis or a confidence level. Slice 8
adds them as a separate value the Diagnostician produces *from* findings,
rather than as optional fields here that this slice would leave permanently
`None`.

### The `ObservabilityPlatform` port exposes vocabulary, not MCP tools

The port offers a small set of methods in this project's terms — for this
slice, one:

```
search_logs(service: str, window: Window, query: str) -> Sequence[LogRecord]
```

The ADK adapter wraps each port method as an ADK `FunctionTool` and gives the
Logs agent nothing else. The model still chooses *whether*, *when*, and *with
what query* to search; what it cannot do is name a Datadog tool.

*Alternative — hand the agent Datadog's `McpToolset` directly.* This is the
more literal reading of "MCP earns its keep where a model discovers and
chooses tools at runtime" in `docs/vision.md`, and it is less code. Rejected:
the agent's instruction would then have to talk about `search_datadog_logs`
and Datadog's query syntax, so a second observability platform would mean
rewriting every specialist agent — precisely what the port exists to prevent,
and a direct violation of `AGENTS.md`'s "a port never types itself against a
vendor SDK's model; translate at the adapter". It also hands the model
Datadog's entire `core` toolset when the Logs agent needs one tool of it.

The trade-off is real and worth naming: bounding the tool surface at the port
means the system gives up runtime tool discovery. MCP stays as the adapter's
*transport* — which is what makes it cheap to widen the port in slice 7 — but
the port, not the server, decides what a specialist can ask for. Widening the
port is a deliberate act, which is the point.

`Window` and `LogRecord` are domain values. `LogRecord` stays thin —
timestamp, level, message, service — because a finding cites evidence a human
reads, not a platform's full log document.

### The Logs agent is one `LlmAgent` with a structured output

An ADK `LlmAgent` given the platform's tools, an instruction scoped to error
and warning patterns in the incident's window, and an `output_schema` for the
findings. Current ADK supports pairing `output_schema` with tools: when both
are set it injects a `set_model_response` tool the model calls with the final
structured payload, which ADK extracts and validates. That removes the reason
to parse free text or to run a second summarising agent.

The pydantic schema is the adapter's own, translated into `Findings` at the
adapter boundary — the domain does not learn what pydantic is, and the import
contract enforces that.

The instruction lives in its own module as a constant so that a unit test can
assert what it asks for (the incident's window, evidence for every
observation, no root cause) without constructing an agent or reaching a model.

### The `Investigator` implementation is a crew today of one

The ADK adapter implements `Investigator` by running the Logs agent and
returning its findings. Slice 7 adds specialists behind the same method and
concatenates their findings; the port, the run, and the report do not change.
The `Signal` on each finding is what keeps a multi-specialist result legible
without changing its shape.

### The run gains an investigation stage, and it never blocks delivery

`ReportBuilder` becomes `Callable[[Incident, Findings | None], TriageReport]`.
`None` means "no findings — the investigation did not complete", which the
domain renders as the honest fallback rather than as an empty investigation.
Two builders live in `domain/report.py`: the investigated one, and today's
pass-through, which stops being "the report before investigation exists" and
becomes "the report when investigation could not run".

In `_handle`, investigation happens only on the due path, inside `_delivered`,
after `should_report` is true. A suppressed report therefore costs nothing,
which the spec requires and which also keeps the cooldown as the bound on
model spend.

`Stage.INVESTIGATE` joins the existing stages so a failure names itself.
`InvestigatorError` is caught where it happens, produces a `RunFailure`, and
the run carries on to build the fallback report and deliver it — the failure
is recorded, delivery is not skipped, and the run finishes unsuccessfully.
This is the "both: degrade and flag" behavior: the team is told, and the exit
status still says something went wrong.

*Alternative — treat investigation failure like a ledger or delivery failure
and skip the group.* Rejected: it would make the system worse than before this
change for exactly the incidents most likely to matter, since a platform
having a bad day is correlated with there being something to report.

### `Investigation` config section; the model credential is environmental

`Config` gains `investigation: Investigation` with a `model` field and a
documented default, resolved by the YAML loader like every other section and
overridable by `INVESTIGATION_MODEL`. What the model *costs* to reach — the
provider credential — is environment-only, validated in the composition root
so a misconfigured deployment refuses to start rather than failing on the
first due incident.

The circuit-breaker fields stay where they are and stay unread. `mcp_*`
breakers are not repurposed as this adapter's timeouts, for the reason
`Ingestion` already documents: equal defaults are not a shared concept.

### The Datadog MCP adapter derives its endpoint from `DD_SITE`

The Datadog MCP server is reached over Streamable HTTP at
`https://mcp.<DD_SITE>/v1/mcp`, restricted to the toolset the port needs, and
authenticated with the `DD_API_KEY` / `DD_APP_KEY` already resolved by
`adapters/datadog/connection.py` — sent as the `DD_API_KEY` and
`DD_APPLICATION_KEY` headers the server expects. No new credential, no new
environment variable, and the existing "refuses to start without them"
behavior covers this adapter too.

### Testing

- `tests/unit/` — the ports' contracts; `Findings` and the report builders;
  the run's investigation stage and its failure path, against a fake
  investigator; the agent instruction's content; the adapter's translation of
  a canned MCP tool response into `LogRecord`s, and of a canned model payload
  into `Findings`. No network, no model.
- `tests/integration/` — the end-to-end run gains a fake investigator, so it
  covers the new stage without gaining a dependency. A live, credential-gated
  test against the real MCP server follows the existing pattern in
  `test_datadog_alert_source_live.py`.

The one thing not unit-testable is the model actually choosing to call the
tool. That is what the credential-gated live test is for, and it is why the
adapter is split so that everything either side of the model call is covered
without one.

## Risks / Trade-offs

- **No bound on an investigation's length or spend.** The breakers exist in
  config and are not enforced until slice 10, so a looping agent runs until
  the process is killed. → The cooldown bounds how *often* an investigation
  happens, and the adapter sets a connection timeout on the MCP transport.
  Accepted deliberately rather than half-implemented; slice 10 is the fix and
  should follow closely.
- **The model may report a pattern the logs do not show.** An agent asked for
  evidence can still fabricate it. → The instruction requires every
  observation to cite retrieved logs, the schema gives evidence its own field
  so an empty one is visible, and the report presents findings as observations
  rather than conclusions. This is mitigated, not solved; slice 8's confidence
  level is where it gets addressed properly.
- **Giving up runtime tool discovery** (see the port decision above). →
  Widening the port is a small, deliberate change, and slice 7 will exercise
  it three times, which is a fair test of whether the boundary is in the right
  place.
- **A new heavyweight dependency.** `google-adk` pulls in a large transitive
  tree, and the import contract must keep it out of the core. → The contract
  already forbids `google` and `mcp` in `domain` and `ports` and walks the
  transitive graph, so the first misplaced import fails the build rather than
  a review.
- **Runs get slower and start costing money.** A run that took seconds now
  makes model and tool calls per due incident. → Only due incidents are
  investigated, so the cooldown already bounds the rate; the README should say
  plainly that a run now incurs model cost.
- **`asyncio.run` per investigation.** Slice 7 makes four specialists
  sequential where they could be concurrent. → Concurrency belongs inside the
  adapter and can be added there without touching the port; this only becomes
  a real cost once there are several specialists to overlap.

## Open Questions

- Which model the default should name. It affects one constant and one README
  line, not the specs, the ports, or the task breakdown, and is best chosen
  against a real investigation rather than in advance.
- Whether the evidence a finding cites should be structured log records or the
  agent's own prose quotation of them. Both satisfy the spec's "a human can
  tell which logs it was drawn from"; the answer will be obvious after reading
  a handful of real reports.
