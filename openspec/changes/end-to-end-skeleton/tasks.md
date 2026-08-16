## 1. The stamp moves off the decision

- [x] 1.1 Change the failing expectation in `tests/unit/test_triage.py`: a
      decision that is due to be reported returns the incident with its alerts
      absorbed and its last-reported instant untouched (specs/triage-ledger -
      The decision and the stamp are separate)
- [x] 1.2 Add a failing test that an incident already reported keeps its
      previous stamp when a later decision is due again, so nothing is lost by
      not stamping (specs/triage-ledger - A due report that could not be
      delivered)
- [x] 1.3 Make them pass by removing the `reported(now)` call from `triage()`,
      leaving `should_report` as the only thing the decision asserts, and
      update the module docstring to say where the stamp is applied now

## 2. The pass-through report

- [x] 2.1 Write a failing test that a report built from an incident names the
      service in its subject and lists every absorbed alert — time, title, and
      link — in its body (specs/triage-run - A report identifies its service
      and alerts)
- [x] 2.2 Write a failing test that the body states the alerts have not been
      investigated (specs/triage-run - The report does not pretend to be
      triage)
- [x] 2.3 Write a failing test covering an alert with no title and no link, so
      the builder handles the defaults `Alert` allows
- [x] 2.4 Implement the builder in `domain/report.py` beside `TriageReport`,
      stdlib-only, producing a valid single-line subject

## 3. The run

- [x] 3.1 Write a failing test that a run with one group and nothing on record
      opens an incident, delivers a report, and records it — driven entirely
      by fakes for the three ports (specs/triage-run - Alerts fired and
      nothing is on record)
- [x] 3.2 Write failing tests for the empty run and the multi-service run:
      no alerts delivers and records nothing and succeeds; several services
      are each decided independently (specs/triage-run - No alerts fired,
      Several services in one run)
- [x] 3.3 Write a failing test that the run asks the alert source for alerts
      from the run's instant minus the configured lookback (specs/triage-run -
      A run fetches over the configured lookback)
- [x] 3.4 Write a failing test that the same supplied instant reaches the
      fetch bound, the decision, and the recorded timestamps, and that two
      runs over the same inputs agree (specs/triage-run - A run decides
      against a single instant)
- [x] 3.5 Implement `app/run.py`: the pipeline over `AlertSource`,
      `TriageLedger`, `Notifier`, an injected report builder, `now`, and
      `new_id`, importing `ports` and `domain` only
- [x] 3.6 Write a failing test that a delivered report is followed by a record
      carrying the report stamp at the run's instant (specs/triage-run -
      Delivery succeeds)
- [x] 3.7 Write a failing test that a failed delivery still records the
      incident with its alerts absorbed and no new stamp, leaving it due next
      run (specs/triage-run - Delivery fails)
- [x] 3.8 Write a failing test that a suppressed report delivers nothing and
      leaves the previous stamp untouched (specs/triage-run - A suppressed
      report is not a delivery)
- [x] 3.9 Implement the deliver-then-record ordering in `app/run.py`

## 4. Failure behavior and the run's outcome

- [x] 4.1 Write a failing test that an `AlertSourceError` ends the run with
      nothing delivered, nothing recorded, and an unsuccessful outcome
      (specs/triage-run - The alert source fails)
- [x] 4.2 Write failing tests that a `NotifierError` on one group and a
      `TriageLedgerError` on another each leave the remaining groups reported
      and recorded, with the run finishing unsuccessfully (specs/triage-run -
      One group's failure does not cost the others their reports)
- [x] 4.3 Write a failing test that a run with no failure finishes
      successfully (specs/triage-run - Every group succeeds)
- [x] 4.4 Write a failing test that each recorded failure names the stage and
      the service it concerns (specs/triage-run - A failure is diagnosable)
- [x] 4.5 Implement `RunOutcome` and the per-group containment in
      `app/run.py`, catching the two port errors named in design.md and no
      others

## 5. Composition root

- [x] 5.1 Write a failing test that the composition root resolves
      configuration, builds the three adapters, and calls the run — asserted
      through substitution at the factory boundary, with no network, no mail
      server, and no database file (specs/triage-run - Adapters are named in
      one place only)
- [x] 5.2 Write failing tests that a missing scope and a deployment with no
      notification channel each refuse to start, name what is missing, and
      fetch nothing (specs/triage-run - Unusable configuration prevents the
      run)
- [x] 5.3 Implement `app/composition.py`, opening the ledger's SQLite
      connection from `resolve_ledger_path` and closing it when the run
      finishes, passing the pass-through builder and a UUID-backed `new_id`
- [x] 5.4 Add a test asserting `app/run.py` imports nothing from
      `alert_triage.adapters`, so the pipeline stays adapter-free as slices
      are added

## 6. Entrypoint

- [x] 6.1 Write a failing test that the entrypoint returns a zero status for a
      run with no failures and a non-zero status otherwise (specs/triage-run -
      A scheduler reads the outcome, A successful run)
- [x] 6.2 Write a failing test that a configuration failure at startup is
      reported and produces a non-zero status rather than a traceback
- [x] 6.3 Implement `app/main.py`: take the run's instant once, configure
      logging in this module alone, call the composition root, and translate
      the outcome into an exit code
- [x] 6.4 Add `src/alert_triage/__main__.py` so `python -m alert_triage` runs
      the same entrypoint
- [x] 6.5 Add the `alert-triage` console script to `[project.scripts]` in
      `pyproject.toml`
- [x] 6.6 Extend `tests/integration/test_installed_distribution.py` with a
      failing test that the console script is installed and reachable from the
      installation (specs/triage-run - The command is part of the installed
      package)

## 7. End to end

- [x] 7.1 Write a failing integration test driving a complete run against
      fakes for all three ports across two runs: the first opens and reports
      an incident, the second continues it inside the cooldown and reports
      nothing (specs/triage-run - A run takes alerts end to end in one pass)
- [x] 7.2 Write a failing integration test that an alert appearing in two
      overlapping lookbacks does not open a second incident (specs/triage-run
      - Alerts seen twice by overlapping runs)
- [x] 7.3 Write a failing integration test over a real on-disk ledger that a
      run whose delivery failed reports the incident on the next run, in a new
      connection (specs/triage-ledger - A due report that could not be
      delivered)

## 8. Documentation and the quality gate

- [x] 8.1 Add a "Running it" section to the README: the command, what a run
      needs in its environment, and what its exit status means
      (specs/triage-run - A first manual run)
- [x] 8.2 Update the README's architecture diagram via the mermaid tool if
      the composition root changes what it shows
- [x] 8.3 Run `uv run ruff check src tests`, `uv run ruff format --check src
      tests`, `uv run mypy`, and `uv run pytest`, and fix anything they report
- [x] 8.4 Run `openspec validate end-to-end-skeleton --strict` and resolve
      anything it reports
