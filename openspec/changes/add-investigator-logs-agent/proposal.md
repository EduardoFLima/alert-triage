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
  conclude anything.
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
- **Investigation failure degrades, it does not block.** When an
  investigation cannot complete, the run delivers the pass-through report it
  delivers today, saying the investigation was attempted and did not finish.
  The team is never worse off than it is before this change. Marking a report
  "investigation incomplete" and routing it through escalation is slice 10's
  work, and needs the escalation path from slice 9 to route to.
- **A failed investigation is retried on the next run, and only a changed
  outcome is reported.** An incident whose report went out without findings is
  investigated again next run, up to three attempts in total. A retry that
  fails again tells nobody anything new, so nothing is delivered. A retry that
  succeeds delivers the findings the first report could not carry, even though
  the cooldown has not elapsed — because that *is* new information. Once the
  attempts are spent, the incident goes back to being governed by the cooldown
  alone.
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
  covering both the investigated report and the degraded fallback.
- `config`: An optional `investigation` section is added, resolved from the
  file or the environment like every other behavior setting, with defaults
  that let a run work with no configuration for it.
- `triage-ledger`: An incident now also carries how many investigation
  attempts it has spent without producing findings, so a retry survives
  between runs. The "one report per incident until the cooldown elapses" rule
  gains its first exception: a retry that finally produces findings is
  reported inside the cooldown.

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
