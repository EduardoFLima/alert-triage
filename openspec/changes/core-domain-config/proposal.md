## Why

The alert triage job needs a domain model to reason about before it can talk to
any external system: what an "alert" is, how alerts combine into one incident
worth investigating once, and where its configuration (most critically, the
mandatory `scope`) comes from. This is slice 1 of the capability breakdown in
`docs/vision.md` — it builds directly on the scaffolding from slice 0 and
everything else (ingestion, ledger, notification, investigation) depends on
these two pieces existing first. Both are pure/unit-testable with no adapters
required yet.

## What Changes

- Add an `Alert` domain entity representing a single incoming alert (service
  tag, timestamp, and the fields grouping depends on).
- Add grouping logic that treats alerts as "the same incident" when they share
  a service tag and fall within the same time window, so a group is
  investigated/reported once rather than per-alert.
- Add a `Config` port (interface) and a YAML-backed adapter that:
  - Loads an optional `config.yaml`; the file's absence is not an error.
  - Applies defaults for `circuit_breakers` when omitted. `critical_services`
    itself is optional with no synthetic default list, but a service that
    *is* declared critical still gets documented default thresholds for any
    key it doesn't explicitly set.
  - Resolves the mandatory `scope` (v1: Datadog team) from `config.yaml` and/or
    environment variable, environment variable winning if both are set, and
    refuses to start if neither source provides it.
  - Supports environment variable overrides for any config value via a
    predictable section/key → `SCREAMING_SNAKE_CASE` naming convention (e.g.
    `SCOPE_DATADOG_TEAM` for `scope.datadog_team`), env var always taking
    precedence.

## Capabilities

### New Capabilities
- `alert-grouping`: Alert entity and the same-service/same-time-window
  grouping logic that decides which alerts are treated as one incident.
- `config`: Config port, optional-YAML loader with section defaults,
  mandatory `scope` resolution with no fallback, and environment variable
  overrides for any config value.

### Modified Capabilities
(none — this is new domain logic, nothing existing to modify)

## Impact

- New code only, under the domain layer per the hexagonal layout from slice 0;
  no adapters, no external I/O beyond reading `config.yaml` and process
  environment variables.
- No breaking changes — nothing depends on this yet.
- Unblocks slice 2 (Alert ingestion), which will produce `Alert` entities via
  an `AlertSource` port adapter, and slice 3+ which consume grouped alerts and
  config values.
