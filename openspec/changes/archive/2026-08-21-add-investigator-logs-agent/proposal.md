## Why

The run works end to end but has nothing to say. Every report it delivers
carries the alerts and the sentence "these alerts have not been
investigated" — the legwork the project exists to do is exactly the part that
is missing, and a team reading one is still left with "figure out where to
even start".

This is slice 6 of the capability slice order in `docs/vision.md`: the first
cut that makes a report worth reading, and the one that proves the ADK + MCP
adapter pattern the remaining specialist agents (slice 7) and the
Diagnostician (slice 8) are all built on. Proving that pattern once, against a
single agent, is cheaper to get wrong than proving it against four.

## What Changes

- **New `Investigator` port** — given an incident, produce findings. The run
  calls it between deciding a report is due and building that report.
- **New `ObservabilityPlatform` port** — what a specialist agent queries for
  evidence around an alert window. Distinct from `AlertSource`: ingestion asks
  one fixed question on a schedule, while an agent discovers and chooses tools
  at runtime, which is where MCP earns its keep.
- **New `Findings` domain value** — what an investigation came back with, in
  this project's vocabulary: observations tied to evidence, with no
  hypothesis and no confidence. Those arrive in slice 8, and a findings value
  that cannot express them is what keeps this slice from pretending to
  conclude anything. A finding describes a pattern and illustrates it with a
  few real examples, rather than carrying every record behind it.
- **Fabricated evidence cannot reach a report.** The evidence in a finding is
  only ever a record the platform actually returned: the agent cites what it
  retrieved and the system reproduces the real record, so invented log lines
  have no path into a report. A finding whose evidence cannot be traced is
  discarded and the discard recorded, while the findings that check out are
  still reported.
- **New ADK adapter: the Logs agent** — an `LlmAgent` whose only tools are the
  observability platform's, instructed to look for error and warning patterns
  in the incident's window and report what it found. It is the whole
  `Investigator` implementation for now; slice 7 adds siblings behind the same
  port.
- **New Datadog MCP adapter** implementing `ObservabilityPlatform`, reaching
  the Datadog MCP server with the credentials already read from the
  environment.
- **The report carries findings.** A report for an investigated incident
  states what was found and the evidence behind it, instead of the
  "not investigated" text.
- **A failed investigation tells nobody anything.** "These alerts fired and we
  could not look at them" carries nothing a team can act on, so it is not sent.
  The incident is still recorded, with its alerts absorbed and the attempt
  spent.
- **A failed investigation is retried on the next run**, up to three attempts
  in total. The bound applies to every investigation of an incident, not only
  the ones after the first: because a failure delivers nothing, the incident
  stays due, and without that bound an unreachable platform would mean one
  investigation per run for as long as the alerts kept firing.
- **Silence has a floor.** Once the attempts are spent and a report is still
  due, the run delivers the alerts-only report — what fired, and that
  investigation could not complete. Alerts that fired are never lost to a
  platform outage; they arrive late instead. This is the pass-through report
  slice 5 already sends, which is why it survives rather than being deleted.
  Marking a report "investigation incomplete" and routing it through
  escalation is slice 10's work, and needs the escalation path from slice 9 to
  route to.
- **New optional `investigation` config section** carrying the model the agent
  crew runs on and how many attempts an investigation gets. Credentials and
  endpoints stay environment-only, as `docs/vision.md` requires.
- The circuit breakers already declared in config stay unenforced. Slice 10
  owns enforcing them; this slice must not quietly half-implement them.

## Capabilities

### New Capabilities
- `investigation`: What an investigation is asked for and what it comes back
  with — the `Investigator` and `ObservabilityPlatform` ports, the findings a
  specialist agent produces, what the Logs agent looks for, and what happens
  when an investigation cannot complete.

### Modified Capabilities
- `triage-run`: The run gains an investigation stage between deciding a report
  is due and building it. The requirement describing the pass-through report
  as what a run sends "before investigation exists" is replaced by one
  covering the investigated report, the silence when an investigation fails,
  and the alerts-only report of last resort.
- `config`: An optional `investigation` section is added, resolved from the
  file or the environment like every other behavior setting, with defaults
  that let a run work with no configuration for it.
- `triage-ledger`: An incident now also carries how many investigation
  attempts it has spent, so a retry survives between runs. The cooldown rule
  itself is untouched — every report a run delivers still happens when the
  cooldown says it may.

## Impact

- **New ports**: `ports/investigator.py`, `ports/observability_platform.py`.
- **New domain**: `domain/findings.py`; `domain/report.py` gains a builder
  that renders findings, keeping the pass-through builder as the fallback;
  `domain/incident.py` gains the attempt counter and `domain/triage.py` the
  rule that reads it.
- **Changed storage**: the ledger's schema gains a column for the attempt
  counter, and its adapter reads and writes it.
- **New adapters**: `adapters/adk/` (the Logs agent and the `Investigator`
  implementation), `adapters/datadog/` gains the MCP-backed
  `ObservabilityPlatform`.
- **Changed**: `app/run.py` (an investigation stage and its failure handling),
  `app/composition.py` (builds and injects the investigator),
  `ports/config.py` and the YAML loader (the `investigation` section).
- **Dependencies**: `google-adk` is added, and with it `google` and `mcp` must
  be listed in the `forbidden_modules` of the "Domain and ports are free of
  vendor libraries" contract in `pyproject.toml` — they already are, so the
  boundary is enforced from the first commit of this change.
- **Environment**: the Datadog MCP endpoint is derived from `DD_SITE` and
  authenticated with the `DD_API_KEY` / `DD_APP_KEY` already required. A model
  credential for the ADK agent is a new deployment fact.
- **Cost and latency**: a run now makes model and tool calls per due incident.
  Reports are already suppressed by the cooldown, so the bound on how often
  this happens exists; the bound on how far one investigation can run does not
  until slice 10.
