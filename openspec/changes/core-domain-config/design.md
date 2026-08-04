## Context

See proposal.md - Why. This slice sits at the base of the domain layer
(hexagonal core) established in slice 0 (`docs/vision.md`, "Capability
slices," item 0). Two independent pieces land together because both are pure
domain/config concerns with no adapters yet: the `Alert` entity + grouping
function, and the `Config` port + YAML/env loader. Nothing downstream exists
yet to consume either, so this design is scoped to shape choices that later
slices (ingestion, ledger, escalation, circuit breakers) will build on without
rework.

## Goals / Non-Goals

**Goals:**
- Define the `Config` port's shape so later slices (circuit breakers,
  escalation's critical-services overrides) can extend it without changing
  its resolution contract.
- Define a deterministic, mechanical env-var-name-from-YAML-path mapping so
  new config values never need bespoke override wiring.
- Keep `Alert` and grouping free of any dependency on Config or on a specific
  observability platform's data shape.

**Non-Goals:**
- Choosing the Datadog MCP adapter's alert schema or field mapping (slice 2).
- Defining `critical_services` tier/threshold schema in full (only that the
  section is optional with no built-in defaults of any kind) — the full
  shape arrives when escalation (slice 9) needs it.
- Circuit breaker key names/values beyond what's already fixed in
  `docs/vision.md`'s table (slice 10 wires them to actual breaker logic).

## Decisions

**Config as a port (interface) + one YAML/env adapter, not a static loader.**
Keeping `Config` a port (returning resolved values) rather than a module-level
loader function matches the hexagonal rule (domain doesn't know its config
source) and lets tests substitute an in-memory config without touching disk
or env vars. Alternative considered: a plain module-level `load_config()`
function — rejected because it couples every consumer to "config comes from
YAML + env," which the architecture explicitly avoids for ports.

**Env var mapping is mechanical: `section.key` → `SECTION_KEY`.**
Nested YAML paths join with `_` and uppercase, e.g. `scope.datadog_team` →
`SCOPE_DATADOG_TEAM`, `circuit_breakers.max_tool_calls_per_agent` →
`CIRCUIT_BREAKERS_MAX_TOOL_CALLS_PER_AGENT`. This is a pure string transform
with no lookup table to keep in sync as config grows — satisfies "room to
grow other settings later without a schema rewrite" from the vision doc.
Alternative considered: an explicit per-key mapping table — rejected as an
extra maintenance burden for no behavioral benefit given the naming
convention is already regular.

**Resolution order: env var, then YAML, then built-in default; merge once at
startup.** The adapter resolves the full config into a single immutable
value at construction time (env checked first per key, falling back to YAML,
falling back to defaults for optional sections), rather than re-resolving on
each access. This matches "the environment variable always takes precedence"
and avoids re-reading env/file state mid-run. Mandatory `scope` resolution
failing raises at this same startup point — fail fast, not on first use.

**Grouping time window is itself a config value, not a hardcoded constant.**
`docs/vision.md` doesn't fix a number for the grouping window, only the rule
("same service tag ... within the same time window"). Treating the window as
a config value (with a sensible default) is consistent with "room to grow
other settings later" and avoids hardcoding something operators will want to
tune per environment. It lives under a new optional config key rather than
`circuit_breakers` or `critical_services` since it's a domain/grouping
concern, not a breaker or an escalation override.

## Risks / Trade-offs

- [Mechanical env var naming can collide for oddly-shaped nested keys, e.g. a
  future `scope_datadog.team` colliding with `scope.datadog_team`] → Keep
  config key names flat and predictable (max two levels: section.key); revisit
  only if a real collision arises.
- [Resolving config once at startup means a running process won't pick up
  env var or file changes without restart] → Acceptable: this is a
  recurring batch job (per vision.md deployment section), not a long-lived
  server: each run starts fresh.
