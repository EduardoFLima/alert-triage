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
- Make evidence discipline *enforced* rather than requested: no finding reaches
  a report unless the logs behind it are ones the platform actually returned.

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
Finding       signal, observation, occurrences, examples: tuple[LogRecord, ...]
Findings      findings: tuple[Finding, ...]
```

A finding is a *pattern* with a bounded number of representative examples, not
a dump of every record behind it. `MAX_EXAMPLES_PER_FINDING = 10` is a domain
constant rather than a config key: it is what makes a finding readable in an
email, not something an operator tunes per team. `occurrences` carries how
often the pattern was seen, so "this happened 400 times" survives without 400
records travelling with it.

The split between `observation`/`occurrences` and `examples` is the split
between what the model *says* and what the platform actually *returned* — see
the evidence decision below, which is what makes it load-bearing rather than
cosmetic.

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
assert what it asks for (the incident's window, a citation for every
observation, a bounded number of examples, no root cause) without constructing
an agent or reaching a model. The instruction is how the agent is asked to
behave; the citation resolution below is what happens when it does not.

### Fabricated evidence cannot reach a report

An instruction that says "cite your evidence" is a request, and a model can
satisfy it with text that looks like a log line and never existed. The fix is
not a better instruction — it is to make the model incapable of *writing*
evidence at all.

Every record the agent ever sees passes through one place: the `search_logs`
tool wrapper. That wrapper retains what the platform returned during this
investigation, keyed by an identifier it assigns as it hands records to the
model. The output schema then gives the model no free-text evidence field.
It cites identifiers:

```
observation:  "OOMKilled recurs roughly every 40s from 14:02"
occurrences:  47
cites:        ["rec_7", "rec_12", "rec_19"]      -> at most MAX_EXAMPLES_PER_FINDING
```

The adapter resolves each citation against the records it retained and builds
`Finding.examples` from the real `LogRecord`s. A citation naming a record that
was never retrieved does not resolve. The consequence is structural: the log
lines a human reads in a report are assembled by us out of what Datadog
actually sent, never out of model output. Invented evidence has no path to the
page.

A citation that does not resolve causes that finding to be **dropped**, with
the unresolvable citation logged so the fabrication is visible to whoever is
tuning the agent. The findings that verified are still reported — a model that
got one thing wrong has not necessarily got the rest wrong, and discarding
real evidence to punish an invented one serves nobody. A finding whose
citations *all* fail to resolve is dropped entirely; if that leaves no findings
at all, the result is an honest empty "nothing notable" rather than a failure,
because the investigation did run.

What this does **not** verify is the model's characterisation: `observation`
and `occurrences` are its own prose and its own arithmetic, and it can still
say "every 40 seconds" over records that are minutes apart. That is a real
residual risk, named in Risks below and bounded by the examples sitting right
beside the claim where a human can see them disagree. Verifying the count
would mean the adapter re-deriving the pattern itself, which is the agent's
job, not the adapter's.

*Alternative — free-text evidence, verified by string-matching it against the
retrieved records.* Rejected: it turns verification into fuzzy matching
against paraphrase, whitespace, and truncation, and the near-misses are
exactly where a fabrication hides. Resolving an identifier is exact and has
one obvious test.

*Alternative — trust the instruction and check nothing.* Rejected: that is
what the previous draft of this document did, while claiming slice 8 would fix
it. It would not have. See Risks.

### The `Investigator` implementation is a crew today of one

The ADK adapter implements `Investigator` by running the Logs agent and
returning its findings. Slice 7 adds specialists behind the same method and
concatenates their findings; the port, the run, and the report do not change.
The `Signal` on each finding is what keeps a multi-specialist result legible
without changing its shape.

### The run gains an investigation stage

`ReportBuilder` becomes `Callable[[Incident, Findings | None], TriageReport]`.
`None` means "no findings — every investigation of this incident failed",
which the domain renders as the honest last-resort report rather than as an
empty investigation. Two builders live in `domain/report.py`: the investigated
one, and today's pass-through, which stops being "the report before
investigation exists" and becomes "the report when investigation never could
run".

In `_handle`, investigation happens inside `_delivered`, after `should_report`
is true and only while attempts remain. An incident inside its cooldown
therefore costs nothing, which keeps the cooldown the bound on how often model
spend happens at all.

`Stage.INVESTIGATE` joins the existing stages so a failure names itself.
`InvestigatorError` is caught where it happens and produces a `RunFailure`, so
the run finishes unsuccessfully even on the runs where it delivered nothing —
without that, a platform outage would look from outside the process exactly
like a quiet night.

*Alternative — treat investigation failure like a ledger or delivery failure
and skip the group entirely.* Rejected in substance but not in appearance:
handling continues for the other groups, and the incident is still recorded
with its alerts and its spent attempt. What is skipped is only the report.

### Retry across runs is one integer on the incident

A failed investigation is retried on the next run, up to three attempts in
total. The whole state this needs is one counter on `Incident`:

```
investigation_attempts: int = 0    # attempts spent without findings reaching the team
```

Two transitions, and only two:

- An investigation that **fails** increments it.
- A report that is **delivered** clears it to `0` — whatever that report
  carried.

The second rule is the existing "the stamp follows the delivery" rule from
`domain/triage.py` applied to a second counter, and it is what makes the
delivery-failure case behave. A successful investigation whose report fails to
deliver leaves the counter untouched, so the next run investigates again and
tries again; clearing it on the investigation's success instead would spend
the attempt on a report nobody received. A successful investigation therefore
never spends an attempt, which is the honest reading of "three attempts".

Clearing on delivery is also what restarts the cycle: an incident that spent
all three attempts, got its alerts-only report, and then kept firing past the
cooldown is investigated afresh with a full allowance, rather than staying
permanently spent.

### Silence on failure, and what it forces

A failed investigation delivers nothing. "These alerts fired and we could not
look at them" is not worth a message while an attempt remains that might say
something better.

That decision has a consequence which is easy to miss and which the earlier
draft of this design got wrong. When nothing is delivered, nothing is stamped,
so the incident stays *due* — permanently. The bound on attempts therefore has
to apply to the **due path as well as the retry path**; otherwise an incident
whose investigation keeps failing is investigated on every run for as long as
its alerts keep firing, which is unbounded model spend during exactly the
outage that caused it. `attempts_remaining` gates every investigation, not
just retries.

The other consequence is that an incident could be investigated three times,
fail three times, and never be reported at all — the alerts would vanish
silently, and a broken observability platform would be indistinguishable from
a quiet night. That is worse than the problem this project exists to solve, so
the spent state has a floor: once the attempts are gone and a report is still
due, the run delivers the alerts-only report. Late, but never silent. The
pass-through builder from slice 5 is what renders it, which is why it survives
this change rather than being deleted.

### The decision stays one question, not two

An earlier draft split the decision into `should_report` and `retry_owed`.
That split turns out to be unnecessary, and seeing why is worth writing down.

A retry is only ever owed after an investigation failed; an investigation only
ever runs when a report is due; and a failure delivers nothing, so the report
stays due. **A retry being owed therefore implies the report is still due** —
`retry_owed` can never be true while `should_report` is false. It carries no
information of its own, and the whole rule reduces to:

```
should_investigate = should_report and attempts_remaining
should_deliver     = should_report and (findings_produced or attempts_now_spent)
```

`should_report` is today's cooldown rule, untouched. `attempts_now_spent` is
evaluated *after* this run's investigation, so the run that spends the last
attempt is the one that delivers the alerts-only report rather than the run
after it.

This is why the re-notify cooldown needs no exception, and why the ledger
delta is smaller than it was: every report a run delivers still happens when
`should_report` is true, exactly as before this change. An earlier draft of
this design introduced a cooldown exception for a successful retry inside the
cooldown; with nothing delivered on failure, that situation is unreachable.

*Alternative — a `last_investigation_failed` boolean beside a counter.*
Rejected: two fields that must agree, where one integer already says both
things.

*Alternative — persist the findings so a retry is not needed after a delivery
failure.* Rejected for this slice: it means storing and versioning findings in
the ledger to save one re-investigation in a rare case, and re-investigating is
both cheap and more current.

One thing worth stating because it is easy to implement backwards:
`findings_produced` means the investigation *completed*, not that it found
something. An investigation that ran and found nothing notable is a result and
is reported as one — "we looked, the logs are clean" is information. Only a
failed investigation is silent.

### `Investigation` config section; the model credential is environmental

`Config` gains `investigation: Investigation` with a `model` field and a
`max_attempts` field defaulting to 3, resolved by the YAML loader like every
other section and overridable by `INVESTIGATION_MODEL` and
`INVESTIGATION_MAX_ATTEMPTS`. What the model *costs* to reach — the provider
credential — is environment-only, validated in the composition root so a
misconfigured deployment refuses to start rather than failing on the first due
incident.

`max_attempts` counts total attempts, not retries after the first, so `1`
disables retrying and `0` is rejected as configuration that would leave an
incident uninvestigable. It is deliberately not `circuit_breakers.max_mcp_retries`
under another name: that bounds one call inside one investigation, this bounds
how many investigations an incident is given across runs, and the two will be
tuned against different evidence — the same argument `Ingestion` already makes
for its own request bounds.

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
  the run's investigation stage, its failure path, and the retry transitions,
  against a fake investigator; the agent instruction's content; the adapter's
  translation of a canned MCP tool response into `LogRecord`s, and of a canned
  model payload into `Findings`. No network, no model.
- Citation resolution is the part worth testing hardest, and it needs no model
  at all: feed the adapter a canned set of retrieved records and a canned model
  payload, and assert what comes out. Resolvable citations become examples;
  a citation to a record never retrieved is dropped; a finding whose citations
  all fail disappears; a payload of nothing but fabrications yields empty
  findings rather than an error. Fabrication is a unit test, not a hope.
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
- **The model may characterise a pattern the logs do not support.** Fabricated
  *evidence* is structurally impossible — the model cannot write a log line,
  only cite one, and an unresolvable citation drops the finding. What survives
  is mis-description: a real set of records summarised as "every 40 seconds"
  when they are minutes apart, or an inflated `occurrences`. → The examples sit
  beside the claim in the report with their real timestamps, so a reader can
  see the two disagree, and the report presents findings as observations rather
  than conclusions.

  An earlier draft of this document deferred this to "slice 8's confidence
  level". That was wrong and is worth recording as wrong: a confidence level is
  produced by the same model that would have fabricated the evidence, so it
  verifies nothing. Nothing in slice 8 addresses fabrication; it is addressed
  here or not at all.
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
- **Retries multiply the cost of a broken platform.** A sustained outage means
  every open incident spends three investigations instead of one, at the worst
  possible moment. → The bound is three and it is per incident, so the extra
  cost is bounded and proportional; an operator who wants none sets
  `max_attempts` to 1.
- **A real incident is reported later than it used to be.** Before this change
  a firing service produced a report on the first run. Now, if the platform is
  unreachable, the team hears nothing until the attempts are spent — three runs
  later. → This is the deliberate trade: a message saying only "we could not
  look" has no action attached to it, and the delay only ever applies when the
  investigation is failing. The floor is that the report always eventually
  arrives, so the delay is bounded and never becomes silence.
- **Escalation-worthy incidents wait too.** The delay above applies to a
  service melting down just as much as to a quiet one, and slice 9's escalation
  path does not exist yet to cut the queue. → Escalation is explicitly designed
  to bypass batching and investigation, so when slice 9 lands it should bypass
  the attempt sequence too. Worth carrying forward as a note on that slice
  rather than pre-building it here.
- **The retry rule is easy to get subtly wrong** — spending an attempt on a
  successful investigation, clearing the counter before delivery, or letting
  the attempt bound apply only to retries and not to the due path — and every
  one of those mistakes is invisible until either an incident goes quiet or the
  bill arrives. → Each transition is specified as a scenario in its own right,
  and the tasks drive each from its own failing test.

## Migration Plan

The ledger's schema gains one column, `investigation_attempts`, defaulting to
`0`. Existing rows therefore read back as "no attempts spent", which is the
correct reading of an incident recorded before the counter existed: it was
reported under the old behavior, and it is entitled to a full allowance of
attempts from here. No backfill, no rewrite of existing records, and a ledger
file from before this change opens and works.

Rollback is the reverse and equally cheap: an older build ignores the column.
Nothing else in the run depends on it.

## Open Questions

- Which model the default should name. It affects one constant and one README
  line, not the specs, the ports, or the task breakdown, and is best chosen
  against a real investigation rather than in advance.
- Whether ten examples per finding is the right number. It is one constant,
  and reading a handful of real reports settles it; the mechanism does not
  change either way.

*(A previous open question — whether evidence should be structured records or
the agent's prose — is now closed by the evidence decision above. It has to be
structured records, because prose is what a model can fabricate.)*
