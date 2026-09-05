## Why

Slice 11 in [`docs/vision.md`](../../../docs/vision.md) is an escalation path:
a severity/threshold rule with per-service overrides, bypassing batching. It is
speculation this PoC has not earned. Its config section, `critical_services`,
has been carried since slice 1 with **zero consumers** — no domain code, no
adapter, no report reads it.

What is actually wanted is smaller and reachable now: scope a run to named
services as well as to an owner, and let a service be marked critical so the
investigation and its report treat it with more urgency.

## What Changes

- **BREAKING** Remove the `critical_services` config section, its
  `CriticalService` settings type, and its `Config.critical_services` port
  property. No backward compatibility and no per-key migration shim.
- **BREAKING** A config section the schema does not resolve is refused by
  name rather than silently ignored, which is what makes the removed section
  discoverable. It also refuses a connection setting written into the
  behavior file, which until now resolved nothing and said nothing.
- **BREAKING** `scope.owner` stops being mandatory on its own. `scope` gains
  an optional `services` mapping, keyed by service name, each entry carrying
  an optional `critical` flag. **At least one of `scope.owner` and
  `scope.services` must resolve, or the run refuses to start.**
- Both keys set means both filters apply — the run watches the named services
  *within* that owner. Listing any service narrows the run to those services.
- `scope.services` is settable from the environment, not file-only:
  `SCOPE_SERVICES` declares the set, `SCOPE_SERVICES_<NAME>_CRITICAL` adjusts
  one entry. A deployment with no config file can scope by service.
- A critical service's incidents carry that fact into `InvestigationTarget`,
  so the crew reasons about it and the written report says it.
- Replace slice 11 in `docs/vision.md`, and remove escalation from the five
  other places that reference it.

## Capabilities

### New Capabilities

None. This reshapes settings and behavior three existing specs already own.

### Modified Capabilities

- `config`: drops two `critical_services` requirements; the mandatory-scope
  requirement is restated as "at least one of owner and services", and the
  `services` mapping and its environment overrides are specified.
- `alert-ingestion`: scope filtering is a conjunction of an optional owner
  filter and an optional service filter, not an owner alone.
- `investigation`: an investigation's target says whether its service is
  critical, and that reaches both the specialists and the report's wording.

## Impact

- `configuration/settings.py`, `configuration/port.py`,
  `configuration/adapters/yaml/loader.py` — the section is removed and
  `Scope` grows; the loader gains its first mapping-valued environment
  override.
- `triage/adapters/datadog/alert_source.py` — the composed query gains an
  optional service term. **Only established live**: per `AGENTS.md`, a
  composed query is proven against a real account, not a fake.
- `investigation/contract.py` (`InvestigationTarget`, `describe()`) and
  `triage/domain/incident.py` — one field, carried across the published
  contract.
- `config.example.yaml`, `config.yaml`, `docs/vision.md`,
  `docs/configuration.md`, `README.md`.
- Slice 12's "trip → partial report + auto-escalate" loses its second half; a
  tripped breaker produces a partial report marked incomplete and nothing
  more.

## Out of scope

- Severity and threshold rules, and anything that bypasses batching. Removed,
  not deferred into this change.
- Scoping by anything other than an owner and a set of service names — tag
  expressions, multiple owners, wildcards.
- Any behavior for `critical` beyond urgency in the investigation's reasoning
  and the report's wording. It does not change cadence, routing, or the
  re-notify cooldown.
