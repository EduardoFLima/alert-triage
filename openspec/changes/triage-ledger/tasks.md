## 1. Incident entity

- [ ] 1.1 Write failing tests for an `Incident` carrying a generated
      identifier, a service, the alerts absorbed into it, and when it was last
      reported — including that the window it spans is derived from its alerts
      rather than stored twice (specs/triage-ledger - Incidents carry a
      generated identity)
- [ ] 1.2 Write a failing test that absorbing further alerts yields an incident
      with the same identifier and an extended window, and that an alert
      already absorbed is not recorded twice (specs/triage-ledger - Identity
      survives the incident growing)
- [ ] 1.3 Implement `domain/incident.py` to pass those tests, stdlib-only

## 2. Continuation rule

- [ ] 2.1 Write a failing test that a group sharing an alert identifier with a
      recorded incident continues it, with no new alerts recorded
      (specs/triage-ledger - Overlapping ingestion windows re-deliver the same
      alerts)
- [ ] 2.2 Write a failing test that a group mixing recorded and unrecorded
      alerts continues the incident and absorbs only the new ones
      (specs/triage-ledger - A firing incident produces new alerts)
- [ ] 2.3 Write a failing test that a group sharing no alert identifier but
      falling within the grouping window of the incident's latest alert
      continues it — asserting the result matches what `group_alerts` would
      have produced from both runs' alerts at once (specs/triage-ledger - A
      burst straddles two runs)
- [ ] 2.4 Write failing tests that a group beyond that window opens a new
      incident, that a service with nothing on record opens a new incident, and
      that the two incidents on one service carry different identifiers
      (specs/triage-ledger - A genuinely separate incident on the same service,
      Alerts for an unrecorded service, Two incidents on one service are
      distinguishable)
- [ ] 2.5 Implement the continuation rule in `domain/triage.py`, taking the id
      factory as an argument so tests supply deterministic identifiers

## 3. Cooldown decision

- [ ] 3.1 Write a failing test that a newly opened incident is reported
      (specs/triage-ledger - A newly opened incident)
- [ ] 3.2 Write failing tests that a continuation inside the cooldown is
      suppressed while still absorbing its alerts, and that a continuation past
      the cooldown is reported (specs/triage-ledger - A continuation within the
      cooldown, A continuation after the cooldown)
- [ ] 3.3 Write a failing test that the cooldown is measured from the most
      recent report, not the first (specs/triage-ledger - The cooldown restarts
      on each report)
- [ ] 3.4 Write a failing test that an incident inside its cooldown does not
      suppress a separate incident on the same service (specs/triage-ledger -
      Suppression is per incident, not per service)
- [ ] 3.5 Write failing tests that the decision is evaluated against a supplied
      instant: the same inputs at the same instant decide the same way, and an
      instant past the cooldown reports without any real time passing
      (specs/triage-ledger - Decisions are made against a supplied instant)
- [ ] 3.6 Extend `domain/triage.py` with the report-versus-suppress decision to
      pass those tests, returning the resulting incident alongside the verdict

## 4. Config additions

- [ ] 4.1 Write failing tests: the re-notify cooldown resolves to its
      documented default when unset, to the YAML value when only the file sets
      it, and to the environment value when both are set (specs/config -
      Re-notify cooldown)
- [ ] 4.2 Add a `ReNotify` section to the `Config` port and resolve it in the
      YAML/env adapter, reusing the existing `section.key` → `SECTION_KEY`
      mapping, with the two-day default from `docs/vision.md`
- [ ] 4.3 Write failing tests: the ledger retention period resolves to a
      thirty-day default when unset and to the operator's value otherwise, and
      changing the cooldown leaves it unchanged (and the reverse)
      (specs/config - Ledger retention period)
- [ ] 4.4 Add a `Ledger` section to the `Config` port carrying the retention
      period, resolved independently of `ReNotify` — a section named for
      re-notification is the wrong home for how long history is kept
- [ ] 4.5 Write failing tests: the ledger storage location resolves from the
      environment, falls back to its documented default when unset, and is
      ignored when written into `config.yaml` (specs/config - Ledger storage
      location comes from the environment)
- [ ] 4.6 Resolve the storage location alongside the other connection settings
      slice 2 established, not in the YAML-backed behavior config

## 5. TriageLedger port

- [ ] 5.1 Write failing tests for the port's shape: synchronous, retrieving the
      incidents on record for a service and recording an incident, in domain
      vocabulary only (specs/triage-ledger - Recorded incidents survive the
      process)
- [ ] 5.2 Define `ports/triage_ledger.py` with a `TriageLedgerError` beside it,
      mirroring how `AlertSourceError` sits beside `AlertSource`

## 6. SQLite adapter — storage

- [ ] 6.1 Write a failing test that a recorded incident is read back with its
      identifier, service, last-reported instant, and every alert's identity,
      timestamp, and provenance intact, against an in-memory connection
      (specs/triage-ledger - Alerts are recoverable from the record)
- [ ] 6.2 Write a failing test that a service with nothing on record returns an
      empty result as a success, against a freshly created schema
      (specs/triage-ledger - First run against empty storage, Nothing on record
      is not a failure)
- [ ] 6.3 Write a failing test that timestamps round-trip as timezone-aware UTC
      values, so no naive datetime escapes the adapter into cooldown arithmetic
- [ ] 6.4 Implement `adapters/sqlite_ledger/` taking an injected
      `sqlite3.Connection` and ensuring its own schema on construction, to pass
      those tests

## 7. Closing, retention, and failure

- [ ] 7.1 Write failing tests that an incident past both the grouping window
      and the cooldown is closed, and one past the window but inside the
      cooldown stays open (specs/triage-ledger - A long-quiet incident closes,
      A quiet but recently reported incident stays open)
- [ ] 7.2 Write failing tests that a closed incident neither continues into a
      later group nor suppresses a later report, so alerts arriving afterwards
      open a new incident with a new identifier (specs/triage-ledger - A closed
      incident is not continued, A closed incident does not suppress a report)
- [ ] 7.3 Write a failing test that retrieval offers only open incidents to a
      decision when a service has both an open incident and a retained closed
      one (specs/triage-ledger - Only open incidents are offered to a decision)
- [ ] 7.4 Write a failing test that the instant an incident closed is stamped
      once and read back unchanged, rather than recomputed — so retuning the
      cooldown does not move it
- [ ] 7.5 Write failing tests that a closed incident within the retention
      period is kept with its alerts and last-reported instant intact, and one
      past the retention period is deleted (specs/triage-ledger - A recently
      closed incident is kept, A long-closed incident is deleted)
- [ ] 7.6 Write a failing test that a retained closed incident leaves the
      decision identical to what it would have been had the record already been
      deleted (specs/triage-ledger - Retained history does not affect triage)
- [ ] 7.7 Write failing tests that a failed read and a failed write each raise
      `TriageLedgerError` rather than returning empty or completing silently
      (specs/triage-ledger - A ledger failure is reported, never disguised)
- [ ] 7.8 Implement closing, retention-bounded deletion on write, and
      vendor-exception translation at the adapter boundary to pass those tests

## 8. Documentation

- [ ] 8.1 Update `docs/vision.md`'s re-notification section with the
      `re_notify.cooldown_seconds` key and its environment equivalent, add the
      `ledger` retention section beside it, and note the persistence choice in
      the slice 3 entry
- [ ] 8.2 Update the README's setup section with the cooldown and retention
      config keys, the ledger storage environment variable and its default,
      what a first run against an empty ledger does, and where to look to read
      the history a closed incident leaves behind

## 9. Verification

- [ ] 9.1 Add an integration test (`tests/integration/`) that records an
      incident to a real file on disk and reads it back through a second
      connection, covering what an in-memory database cannot
- [ ] 9.2 Run `uv run ruff check src tests`, `uv run ruff format --check src
      tests`, `uv run mypy`, and `uv run pytest`; all four pass
- [ ] 9.3 Confirm no domain or ports module imports the adapter, and that the
      `TriageLedger` port's signature names no storage type
