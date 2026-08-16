## Context

See `proposal.md` — Why. What matters for the design is what already exists:
every port this slice needs is defined, every adapter it needs is built and
exposes a factory the composition root can call (`load_config`,
`resolve_connection` + `build_alert_source`, `resolve_ledger_path` +
`SqliteTriageLedger`, `resolve_notifier`), and the domain already answers every
question the pipeline has to ask (`group_alerts`, `triage`, `Incident`,
`TriageReport`).

Two constraints shape everything below. `app/` is the only layer allowed to
name an adapter, and it is the only layer that has never had a line of code in
it. And the domain reads no clock and generates no identifier — `triage()`
takes `now` and `new_id` as arguments — so whatever calls it has to supply
both.

## Goals / Non-Goals

**Goals:**

- One orchestration function that depends on ports only, so a complete run is
  exercisable in a unit test with no I/O at all.
- An ordering that cannot start a cooldown on a report that was not delivered.
- Failure containment at the granularity of a group, with the run's overall
  outcome still legible to a scheduler.
- A seam where slice 8's report generation drops in without the pipeline
  changing shape.

**Non-Goals:**

- Concurrency. Groups are handled one after another; every port is synchronous
  by design and v1 volumes do not justify an executor.
- Command-line options. Configuration comes from `config.yaml` and the
  environment, which is the boundary `docs/vision.md` draws; adding flags would
  create a third source of settings for no v1 benefit.
- Scheduling. The job runs once and exits; what invokes it repeatedly is slice
  12's problem.
- Retry. A failed delivery is retried by the next run, which is the ledger's
  existing behavior rather than a new mechanism.

## Decisions

### The run is a function over ports; the wiring is a separate module

`app/` gets two modules with sharply different jobs:

- `app/run.py` — the pipeline. Takes an `AlertSource`, a `TriageLedger`, a
  `Notifier`, the settings it needs, `now`, and `new_id`. Imports `ports` and
  `domain` and nothing else. Every scenario in `specs/triage-run` is testable
  against it with three fakes.
- `app/composition.py` — the composition root. Resolves configuration, builds
  the three adapters, opens and closes the ledger's connection, and calls the
  run. This is the only module in the project that imports `adapters`.

`app/main.py` is the entrypoint: configure logging, call the composition root,
translate its outcome into an exit code. Keeping it separate from
`composition.py` means the wiring is testable without a process boundary.

Alternative considered: a single `Pipeline` class holding its dependencies as
attributes. Rejected — the run has one method and no state between calls, so a
class would only hide the argument list that makes its dependencies obvious.

### The run returns an outcome; only `main` deals in exit codes

`run.py` returns a small `RunOutcome` value — how many groups it handled, how
many reports it delivered, and the failures it accumulated (each naming a stage
and a service). `main.py` maps "no failures" to 0 and anything else to 1.

Alternative considered: raising on failure. Rejected — a run that partially
succeeded has to describe *both* halves, and an exception carrying a list of
successes is a value in disguise. It also makes the spec's "one group's failure
does not cost the others" directly assertable: the test reads the outcome
rather than parsing log output.

### Deliver, then record — and record either way

Per group: read the open incidents for its service, reach a `TriageDecision`,
and then

1. if a report is due, build it and deliver it; on success stamp the incident
   as reported at the run's instant,
2. record the incident — stamped if delivery succeeded, unstamped if it did
   not, and unstamped when nothing was due.

Recording after a failed delivery is deliberate: the alerts still belong to the
incident, and dropping them would make the next run re-derive a group it has
already seen and possibly open a second incident for it.

The residual gap is a delivery that succeeds and a record that then fails: the
team has the report and the ledger does not know, so the next run reports it
again. The alternative — record first, deliver after — turns the same failure
into silence, and a duplicate report is a smaller harm than a report nobody
gets. The gap is accepted and named here rather than papered over.

### `triage()` stops stamping the incident it returns

Today `triage()` returns `incident.reported(now)` when the incident is due,
which was harmless when nothing could deliver anything. It now returns the
incident with its alerts absorbed and nothing else; the caller applies
`Incident.reported(now)` after a channel accepts the report. `TriageDecision`
keeps both fields and both meanings — it says *whether*, not *that it
happened*.

Alternative considered: leaving `triage()` as it is and having the run
reconstruct an unstamped incident on failure. Rejected — that means the run
undoing a domain decision, and there is no honest way to un-stamp an incident
that was stamped for an event that never occurred.

### Report generation enters through an injected builder

The run takes a `Callable[[Incident], TriageReport]`. This slice passes the
pass-through builder that lives in `domain/report.py` beside the value it
builds; slice 8 passes an adapter instead and the run does not change. The
callable is deliberately not a new port — a port is warranted once report
generation can fail in a way a caller must distinguish, which is slice 8's
question to answer, not this slice's to guess at.

### One instant, taken at the top

`main` takes `datetime.now(UTC)` once and hands it down. The run never reads a
clock, exactly as the domain never does, which is what makes "a run is
reproducible at a supplied instant" a test rather than an aspiration.

### A failed fetch ends the run; everything else is contained

`AlertSourceError` escapes the group loop because there is no loop to reach —
the fetch happens once, before any grouping. `TriageLedgerError` and
`NotifierError` are caught per group, recorded as failures in the outcome, and
the next group proceeds. The three exception types already exist beside their
ports for exactly this: the run distinguishes the failures without importing
anything from an adapter.

### Logging is configured in `main`, used everywhere

The run logs through a module-level `logging` logger and never prints.
`main.py` is the only place a handler or a level is configured, so importing
the pipeline into a test or a future service configures nothing on its
caller's behalf.

## Risks / Trade-offs

- **A duplicate report when recording fails after delivery** → Accepted and
  documented above; the alternative failure mode is silence.
- **A partial fan-out counts as delivered** — one channel accepting starts the
  cooldown even though another failed → This is slice 4's specified behavior
  ("delivery has failed only when no channel accepted the report"); the run
  should not second-guess the port it was handed.
- **One ledger read per group** → N small queries per run. Fine at v1 volumes
  (a handful of services per run) and the port's shape — "open incidents for
  this service" — is what keeps the domain rule out of SQL. Revisit if a run
  ever handles hundreds of groups.
- **A run that fails at startup tells the team nothing** — configuration errors
  surface on stderr and in the exit status, and nothing is delivered, because
  the notifier may itself be what failed to resolve → Acceptable for a manual
  v1 run; a scheduled deployment (slice 12) is where a non-zero exit becomes
  an alert of its own.
- **The pass-through report is not triage** → It says so in its own body, and
  it exists to prove the pipeline rather than to be useful. It is expected to
  be short-lived; slice 8 replaces it.

## Migration Plan

Nothing to migrate: no persisted format changes, and the ledger's schema is
untouched. The only compatibility note is internal — `triage()` returns an
unstamped incident, so its existing unit tests change with it in the same
commit. Rollback is a revert; a ledger written by this slice is read
identically by the previous one.
