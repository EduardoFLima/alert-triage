## MODIFIED Requirements

### Requirement: Mandatory scope with no fallback
The system SHALL require a resolvable `scope`, and SHALL NOT apply a default
or "watch everything" fallback. `scope` is satisfied by either of two
independent keys, each optional on its own and resolvable from `config.yaml`,
an environment variable, or both:

- `scope.owner` — the owner whose alerts are watched (v1: a single team),
  resolved from `SCOPE_OWNER`.
- `scope.services` — the services whose alerts are watched, resolved from
  `SCOPE_SERVICES`.

**At least one SHALL resolve.** The system SHALL refuse to start when neither
does. Settings SHALL be named in platform-neutral terms so that an alert
source for a different observability platform supplies them without the name
lying about where they came from; translating either into a platform's own
query vocabulary is the alert source adapter's responsibility, not the
config's.

An empty `scope.services` SHALL be treated as unset rather than as a filter
matching no service, so that an empty mapping never silently reduces a run to
watching nothing.

#### Scenario: Scope provided only in config file
- **WHEN** `config.yaml` sets `scope.owner` and no corresponding environment
  variable is set
- **THEN** the system starts using the value from `config.yaml`

#### Scenario: Scope provided only via environment variable
- **WHEN** no `config.yaml` exists (or it omits `scope`) and the `SCOPE_OWNER`
  environment variable is set
- **THEN** the system starts using the environment variable's value

#### Scenario: Scope satisfied by services alone
- **WHEN** `scope.services` names at least one service and no owner resolves
  from either source
- **THEN** the system starts, watching those services

#### Scenario: Scope satisfied by both keys
- **WHEN** both `scope.owner` and `scope.services` resolve
- **THEN** the system starts with both in effect, neither overriding the other

#### Scenario: Scope missing from both sources
- **WHEN** neither `scope.owner` nor `scope.services` resolves from
  `config.yaml` or the environment
- **THEN** the system refuses to start and reports that `scope` requires an
  owner, services, or both

#### Scenario: An empty services mapping does not satisfy scope
- **WHEN** `config.yaml` sets `scope.services` to an empty mapping and no
  owner resolves
- **THEN** the system refuses to start, as though `scope.services` were absent

#### Scenario: Owner is expressed in the platform's terms by the adapter
- **WHEN** the resolved owner is used to fetch alerts from an observability
  platform
- **THEN** the adapter translates it into that platform's own way of
  expressing ownership, and the config exposes no platform-specific form

## ADDED Requirements

### Requirement: Services in scope are named, and may be declared critical
`scope.services` SHALL be a mapping keyed by service name, so that a name is
structurally mandatory and cannot be omitted from an entry. Each entry's
settings are optional and an entry MAY be written with none of them.

An entry SHALL support a `critical` flag, defaulting to false. Criticality
SHALL carry no meaning for what is watched — it never adds or removes a
service from scope — and SHALL affect only the urgency with which an
incident on that service is investigated and reported.

#### Scenario: A service is listed without settings
- **WHEN** `config.yaml` lists a service under `scope.services` with an empty
  entry
- **THEN** the service is in scope and is not critical

#### Scenario: A service is declared critical
- **WHEN** `config.yaml` lists a service under `scope.services` with
  `critical: true`
- **THEN** the service is in scope and is critical

#### Scenario: Criticality does not decide membership
- **WHEN** `scope.services` lists one critical and one non-critical service
- **THEN** both services are equally in scope

### Requirement: The environment declares the services in scope, replacing the file
The system SHALL allow the whole set of services in scope to be declared from
the environment through `SCOPE_SERVICES`, as service names separated by
commas, so that a deployment with no `config.yaml` can scope by service.

When `SCOPE_SERVICES` is set it SHALL **replace** the file's `scope.services`
section entirely rather than merging with it: the resolved set is exactly the
names it lists, and settings the file recorded for services it does not list
SHALL NOT survive. A per-entry variable following the documented
section/key naming convention — `SCOPE_SERVICES_<NAME>_CRITICAL` — SHALL then
adjust an entry of whichever set resulted.

#### Scenario: Environment declares services with no config file
- **WHEN** no `config.yaml` exists and `SCOPE_SERVICES` names two services
- **THEN** the system starts with exactly those two services in scope, neither
  critical

#### Scenario: Environment replaces the file's services
- **WHEN** `config.yaml` lists `checkout` as critical and `SCOPE_SERVICES`
  names only `payments`
- **THEN** the resolved scope holds `payments` alone, and `checkout` is
  neither in scope nor critical

#### Scenario: A per-service variable sets criticality
- **WHEN** a service is in scope and
  `SCOPE_SERVICES_<NAME>_CRITICAL` is set to a true value
- **THEN** that service is critical, whether the set came from the file or
  from `SCOPE_SERVICES`

#### Scenario: The file's services stand when the environment declares none
- **WHEN** `config.yaml` lists services under `scope.services` and
  `SCOPE_SERVICES` is not set
- **THEN** the file's services and their settings are the resolved scope

## REMOVED Requirements

### Requirement: Optional critical_services section
**Reason**: The `critical_services` section existed only to carry the
escalation path this change removes, and has never had a consumer. Declaring
a service critical is now an entry under `scope.services`.

**Migration**: None. This is a PoC and the removed section was inert; a
deployment that set it moves the service name under `scope.services` with
`critical: true`. `critical_services` becomes an unknown key and is refused
like any other, which is how a deployment learns it moved.

### Requirement: Threshold defaults within a declared critical service
**Reason**: The per-service thresholds (`tier`, `latency_threshold_ms`) only
ever fed the severity/threshold rule of the escalation path, which this change
removes. A critical service now carries a flag and no thresholds.

**Migration**: None. No threshold key has a replacement, because nothing
consumed one.
