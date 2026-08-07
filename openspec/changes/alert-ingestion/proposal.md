## Why

The domain can group alerts (slice 1) but nothing produces alerts to group —
every slice after this one needs real `Alert` values arriving from somewhere.
This is slice 2 of the capability breakdown in `docs/vision.md`: the
`AlertSource` port and its first adapter, which fetches the alerts belonging to
the configured `scope` team and translates them into the domain's vocabulary.

It also corrects a transport choice `docs/vision.md` made for this port.
Ingestion asks one fixed question on a schedule and needs a deterministic,
typed answer; MCP exists to let an LLM discover and choose tools. That fits the
`ObservabilityPlatform` port, whose consumers are the specialist agents
(slice 6), not this one. Ingestion uses Datadog's REST API instead.

## What Changes

- Add an `AlertSource` port: fetch the alerts in scope that fired since a given
  instant, returning domain `Alert` values. Synchronous — its adapter makes
  ordinary blocking HTTP calls, and nothing here needs an event loop.
- Add a Datadog adapter implementing it against the Events API v2 search
  endpoint, filtering to the configured owner and time range, following cursor
  pagination, and translating each event into an `Alert`.
- **BREAKING** Rename `scope.datadog_team` to `scope.owner` (and
  `SCOPE_DATADOG_TEAM` to `SCOPE_OWNER`). Slice 1 named the setting after the
  platform it happened to target first; adding the port that consumes it makes
  the leak concrete — translating the owner into a `team:` query term is the
  adapter's job, and the config should not preempt it. No deployment exists to
  migrate.
- Extend the `Alert` entity with the identity and provenance ingestion can
  supply: a stable source identifier, the alert's title, and a link back to
  Datadog. A report naming a service but not which alerts fired is not
  actionable, and these come from the payload the adapter already parses.
- Draw an explicit line through configuration: `config.yaml` describes
  behavior only. How far back a run looks for alerts is behavior and lives
  there; the Datadog site and API credentials describe how to *reach* the
  platform and are resolved from the environment only, never from the file.
- Give ingestion its own request timeout and retry bound, so the first
  component making real network calls does not make unbounded ones. These are
  separate settings from the `mcp_*` circuit breakers, which bound
  investigation and are left untouched for slice 10.
- Update `docs/vision.md` so the `AlertSource` port's adapter is described as
  REST rather than MCP, keeping the source of truth consistent with the code.

## Capabilities

### New Capabilities
- `alert-ingestion`: The AlertSource port and its Datadog adapter — scope
  filtering, the lookback window, translation of platform events into `Alert`
  entities, handling of events that carry no service tag, pagination, and the
  bounds a fetch runs under.

### Modified Capabilities
- `alert-grouping`: the `Alert` entity gains identity and provenance fields
  alongside the service tag and timestamp it already carries.
- `config`: renames `scope.datadog_team` to the platform-neutral
  `scope.owner`; establishes that `config.yaml` carries behavior settings
  only; adds the ingestion lookback and ingestion's own request bounds; and
  puts platform connection settings — site and credentials — in the
  environment exclusively.

## Impact

- New `ports/alert_source.py` and a new `adapters/datadog/` implementation; the
  existing `adapters/datadog/` package is currently an empty placeholder.
- `domain/alert.py` gains fields. Nothing consumes `Alert` yet beyond grouping,
  which reasons only about `service` and `fired_at`, so no behavior breaks.
- New runtime dependency `datadog-api-client`, which must also be added to the
  `forbidden_modules` list of the "Domain and ports are free of vendor
  libraries" contract in `pyproject.toml`.
- `ports/config.py`'s `Scope` field is renamed, along with its YAML key, its
  environment variable, and the slice 1 tests naming them.
- `docs/vision.md` edited: the `AlertSource` port line, the slice 2 entry, the
  `scope` description and its `SCOPE_DATADOG_TEAM` example, and the claim that
  every config value has an environment override.
- No breaking changes — nothing downstream exists to break.
- Unblocks slice 3 (TriageLedger) and slice 5 (the end-to-end skeleton), which
  need a real source of alerts to dedup and to run through.
