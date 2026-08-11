## Why

Slice 2 produces alerts and slice 1 groups them, but every run starts from
nothing: the same still-firing incident is regrouped and would be reported
again on every schedule tick, and the deliberately generous ingestion lookback
guarantees consecutive runs see overlapping alerts. Nothing yet remembers what
has already been reported.

This is slice 3 of the capability breakdown in `docs/vision.md`: the
`TriageLedger` port and its first adapter — the memory that turns a stream of
recomputed groups into incidents with continuity, so a group is reported once
and not re-reported until the configured cooldown has passed.

## What Changes

- Add an `Incident` domain entity: an alert group that has been given a
  **generated, stable identity** plus the alerts absorbed into it so far and
  the window they span. Identity is assigned once and never derived from the
  contents, so an incident that grows new alerts keeps the same id rather than
  becoming a different thing each run.
- Add the pure triage decision to the domain: given a freshly grouped
  `AlertGroup`, the incidents already on record, the current instant, and the
  cooldown, decide whether this is a **continuation** of a known incident or a
  new one, and whether it is **due to be reported** or suppressed. A group
  continues an incident when it shares the service *and* either shares an alert
  identifier with it or its earliest alert falls within the grouping window of
  the incident's latest alert — the same predicate `group_alerts` already
  applies inside a single run, applied across runs.
- Add a `TriageLedger` port: retrieve the incidents on record for a service,
  and record an incident's state after a run. Persistence only — the port
  stores and retrieves, it does not decide. Synchronous, matching
  `AlertSource`.
- Add a SQLite adapter implementing the port, over the standard library's
  `sqlite3`. One file, real transactions, and durable across runs, which is
  what makes dedup work for the manual/local v1 deployment.
- **Close** an incident once it can no longer affect any decision — past both
  the cooldown and the continuation window. A closed incident is inert: it can
  neither be continued by later alerts nor suppress a later report.
- **Retain** closed incidents for a configurable period, defaulting to thirty
  days, so a human can go back and see what was reported, when, and for which
  alerts. Deletion happens only after that, which is what keeps the ledger from
  growing without bound. Retention is deliberately its own setting rather than
  a bound derived from the cooldown: how long history is kept and how often a
  report repeats answer different questions.
- Add a `re_notify` config section carrying `cooldown_seconds`, defaulting to
  the two days `docs/vision.md` specifies, resolved under the existing
  environment-wins precedence as `RE_NOTIFY_COOLDOWN_SECONDS`. The retention
  period gets its own `ledger` section rather than joining it, since a section
  named for re-notification is the wrong home for how long history is kept.
- Resolve the ledger's storage location from the environment only. Where a
  database file lives is a deployment fact, not triage behavior, so it lands on
  the environment side of the line slice 2 drew — with a documented default, as
  it is a path and not a credential.

## Capabilities

### New Capabilities
- `triage-ledger`: incident identity across runs — the generated id, the rule
  by which a regrouped set of alerts continues a known incident or opens a new
  one, the re-notify cooldown that suppresses a repeat report, what the ledger
  must remember and hand back, when an incident closes and stops affecting
  decisions, how long its record is then kept for reference, and the
  requirement that a ledger failure is reported rather than disguised as a
  quiet period.

### Modified Capabilities
- `config`: adds the `re_notify` cooldown and the ledger retention period as
  behavior settings with documented defaults, resolved independently of each
  other, and puts the ledger's storage location in the environment
  exclusively, under the boundary the previous slice established.

## Impact

- New `domain/incident.py` (the `Incident` entity) and `domain/triage.py` (the
  continuation and cooldown decision, pure). Both stdlib-only, as the domain
  requires.
- New `ports/triage_ledger.py` with the port and a `TriageLedgerError` defined
  beside it, mirroring `AlertSourceError`.
- New `adapters/sqlite_ledger/` implementing the port. No new runtime
  dependency — `sqlite3` is standard library — so the `forbidden_modules`
  contract in `pyproject.toml` is untouched.
- `ports/config.py` gains a `ReNotify` section carrying the cooldown and a
  `Ledger` section carrying the retention period, with a `Config` property for
  each; the YAML loader in `adapters/yaml_config/` resolves both.
- No change to `Alert`, to `group_alerts`, or to the `AlertSource` port and its
  Datadog adapter. Grouping keeps producing `AlertGroup` values; the ledger is
  what gives them continuity.
- Nothing is wired together yet — there is still no composition root. Slice 5
  is what runs ingestion → grouping → ledger → notifier end to end, and it is
  the first consumer of this port.
- Unblocks slice 5, and settles the concern slice 2 deferred to here: with the
  ledger in place, overlapping ingestion windows are safe.
