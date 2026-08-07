## 1. Dependency and boundary

- [ ] 1.1 Add `datadog-api-client` to the project dependencies, and in the same
      change add it to the `forbidden_modules` list of the "Domain and ports
      are free of vendor libraries" contract in `pyproject.toml`
- [ ] 1.2 Confirm the architecture test still passes and would fail on a stray
      import: temporarily import the SDK from a domain module, watch the
      contract fail naming the module and import, then revert

## 2. Alert entity fields

- [ ] 2.1 Write failing tests for an `Alert` carrying a source identifier,
      title, and link alongside service and timestamp (specs/alert-grouping -
      Alert entity)
- [ ] 2.2 Write a failing test that two alerts differing only in the added
      fields still group together (specs/alert-grouping - Alert entity,
      "Grouping ignores the added fields")
- [ ] 2.3 Extend `Alert` to pass those tests, leaving the grouping logic
      untouched

## 3. Config additions

- [ ] 3.0 Rename `scope.datadog_team` to `scope.owner` and `SCOPE_DATADOG_TEAM`
      to `SCOPE_OWNER` across the `Config` port, the YAML/env adapter, and the
      slice 1 tests, updating those tests first so the rename is driven by
      them (specs/config - Mandatory scope with no fallback)
- [ ] 3.1 Write failing tests: the ingestion lookback resolves to its
      documented default when unset, and to the operator's value from YAML or
      environment with environment winning (specs/config - Ingestion lookback
      window)
- [ ] 3.2 Write failing tests: ingestion's request timeout and retry bound
      resolve to their documented defaults when unset, and changing an
      investigation circuit breaker leaves them unchanged (and the reverse)
      (specs/config - Ingestion request bounds are its own settings)
- [ ] 3.2a Extend the `Config` port and the YAML/env adapter with the lookback
      and ingestion's two request bounds, reusing the existing `section.key` →
      `SECTION_KEY` mapping and leaving `circuit_breakers` untouched
- [ ] 3.3 Write failing tests: a site or credential key written into
      `config.yaml` is not used to reach the platform, and resolution proceeds
      as if it were absent (specs/config - config.yaml describes behavior, not
      connections)
- [ ] 3.4 Write failing tests: the site and credentials resolve from the
      environment under the platform's conventional names, the site falls back
      to its documented default, and absent credentials are reported
      (specs/config - Platform connection settings come from the environment)
- [ ] 3.5 Implement connection-settings resolution to pass those tests, as a
      type separate from the YAML-backed behavior config so the two cannot be
      confused at a call site

## 4. AlertSource port

- [ ] 4.1 Write failing tests for the `AlertSource` port's shape: a
      synchronous fetch taking the time bound and returning domain `Alert`
      values (specs/alert-ingestion - Alerts fetched in this project's
      vocabulary)
- [ ] 4.2 Define the `AlertSource` port in `ports/`, with an
      `AlertSourceError` beside it mirroring how `ConfigError` sits beside
      `Config`

## 5. Datadog adapter — translation

- [ ] 5.1 Write failing tests translating a canned event payload into an
      `Alert`, asserting every field including a timezone-aware UTC
      `fired_at` (specs/alert-ingestion - Translation of platform alerts into
      Alert entities)
- [ ] 5.2 Write a failing test that an event carrying no `service:` tag is
      excluded while its siblings are returned (specs/alert-ingestion -
      Alerts without a resolvable service are excluded)
- [ ] 5.3 Implement the adapter's event → `Alert` translation, taking an
      injected API client, to pass those tests

## 6. Datadog adapter — querying

- [ ] 6.1 Write a failing test asserting the request translates the configured
      owner into the platform's ownership term and carries the requested time
      bound (specs/alert-ingestion - Only alerts within the configured scope,
      Only alerts within the requested time bound)
- [ ] 6.2 Write a failing test that a result spanning several cursor pages
      returns alerts from every page (specs/alert-ingestion - Complete results
      across pagination)
- [ ] 6.3 Write a failing test that a run matching nothing succeeds with no
      alerts (specs/alert-ingestion - No alerts is a valid result)
- [ ] 6.4 Implement scoped, time-bounded querying with cursor pagination to
      pass those tests

## 7. Datadog adapter — failure and bounds

- [ ] 7.1 Write failing tests that a rejected credential and a failure
      part-way through pagination each raise `AlertSourceError` rather than
      returning empty or partial results (specs/alert-ingestion - A failed
      fetch is reported, not disguised)
- [ ] 7.2 Write failing tests that the client is constructed with ingestion's
      own request timeout and retry bound, and that the `mcp_*` breaker values
      have no effect on it (specs/alert-ingestion - Bounded fetching)
- [ ] 7.3 Implement vendor-exception translation at the adapter boundary and
      map ingestion's two request bounds onto the client's timeout and retry
      configuration

## 8. Documentation

- [ ] 8.1 Update `docs/vision.md`: the `AlertSource` port line and the slice 2
      entry now describe a REST adapter, with a sentence on why MCP stays with
      `ObservabilityPlatform`
- [ ] 8.1a Update `docs/vision.md`'s config section for the `scope.owner`
      rename, including the `SCOPE_DATADOG_TEAM` example used to illustrate
      the env-var naming convention
- [ ] 8.2 Update the README's setup section: the lookback config key, the site
      and credential environment variables, and the behavior-versus-connection
      rule that decides which of the two a new setting belongs in
- [ ] 8.3 Update `docs/vision.md`'s config section, which currently says "any
      value normally set in `config.yaml` can instead be set via an
      environment variable" without noting that some values are environment-
      only

## 9. Verification

- [ ] 9.1 Add an integration test (`tests/integration/`) that exercises the
      adapter against a real credential and confirms the event payload shape
      the unit tests assume, skipping cleanly when no credential is present
- [ ] 9.2 Run `uv run ruff check src tests`, `uv run ruff format --check src
      tests`, `uv run mypy`, and `uv run pytest`; all four pass
- [ ] 9.3 Confirm no domain or ports module imports the Datadog SDK, and that
      `AlertSource`'s signature names no vendor type
