## Purpose

Defines the Config port and its YAML/environment-backed resolution rules,
including the mandatory `scope` value with no fallback, so every execution
context (manual, container, GKE/Cloud Run) can supply configuration
consistently without a schema rewrite.

## Requirements

### Requirement: Optional config file
The system SHALL treat the presence of `config.yaml` as optional. Its absence
SHALL NOT be treated as an error by itself.

#### Scenario: No config file present
- **WHEN** the application starts and no `config.yaml` exists
- **THEN** the system proceeds to resolve configuration from defaults and
  environment variables only, without raising a missing-file error

### Requirement: Defaults for optional sections
The system SHALL apply built-in defaults for the `circuit_breakers` section
when it is absent from `config.yaml`.

#### Scenario: Config file omits circuit_breakers
- **WHEN** `config.yaml` is present but does not include a `circuit_breakers`
  section
- **THEN** the system resolves circuit breaker thresholds to their documented
  defaults

### Requirement: Optional critical_services section
The system SHALL treat `critical_services` as entirely optional. Its absence
means no service is treated as critical — the system SHALL NOT invent a
default list of critical services or apply critical-service behavior to any
service that isn't listed.

#### Scenario: Config file omits critical_services
- **WHEN** `config.yaml` is present but does not include a
  `critical_services` section
- **THEN** the system proceeds with no service treated as critical and no
  per-service overrides in effect

### Requirement: Threshold defaults within a declared critical service
When a service is listed under `critical_services`, the system SHALL
recognize it as critical and, for any threshold key not explicitly set for
that service, SHALL apply the documented default threshold value — the
partial entry does not lose default coverage for the keys it leaves
unspecified.

#### Scenario: Config file partially specifies a service entry
- **WHEN** `config.yaml` lists a service under `critical_services` with only
  some of its threshold keys set
- **THEN** the system treats the service as critical, keeps the explicitly
  specified threshold values, and resolves the omitted threshold keys to
  their documented defaults

### Requirement: Mandatory scope with no fallback
The system SHALL require a `scope` value naming the owner whose alerts are
watched (v1: a single team), resolved from `config.yaml`, an environment
variable, or both. The setting SHALL be named in platform-neutral terms —
`scope.owner`, resolved from `SCOPE_OWNER` — so that an alert source for a
different observability platform supplies it without the name lying about
where it came from; translating the owner into a platform's own query
vocabulary is the alert source adapter's responsibility, not the config's.
The system SHALL NOT apply a default or "watch everything" fallback, and SHALL
refuse to start if `scope` cannot be resolved from either source.

#### Scenario: Scope provided only in config file
- **WHEN** `config.yaml` sets `scope.owner` and no corresponding environment
  variable is set
- **THEN** the system starts using the value from `config.yaml`

#### Scenario: Scope provided only via environment variable
- **WHEN** no `config.yaml` exists (or it omits `scope`) and the `SCOPE_OWNER`
  environment variable is set
- **THEN** the system starts using the environment variable's value

#### Scenario: Scope missing from both sources
- **WHEN** `config.yaml` does not set `scope.owner` and `SCOPE_OWNER` is not
  set
- **THEN** the system refuses to start and reports that `scope` is required

#### Scenario: Owner is expressed in the platform's terms by the adapter
- **WHEN** the resolved owner is used to fetch alerts from an observability
  platform
- **THEN** the adapter translates it into that platform's own way of
  expressing ownership, and the config exposes no platform-specific form

### Requirement: Environment variable overrides for any config value
The system SHALL allow any value normally set in `config.yaml` to instead be
set via an environment variable, using a predictable naming convention
mapping the section/key path to `SCREAMING_SNAKE_CASE`. When both a YAML
value and its corresponding environment variable are present, the
environment variable SHALL take precedence.

#### Scenario: Environment variable overrides YAML value
- **WHEN** `config.yaml` sets `scope.owner` to one value and the `SCOPE_OWNER`
  environment variable is set to a different value
- **THEN** the system resolves `scope.owner` to the environment variable's
  value

#### Scenario: Override applies beyond scope
- **WHEN** a non-scope config value (e.g. a circuit breaker threshold) is set
  in both `config.yaml` and its corresponding environment variable
- **THEN** the system resolves that value to the environment variable's
  value, following the same precedence rule as `scope`

### Requirement: config.yaml describes behavior, not connections
`config.yaml` SHALL describe only how the system behaves — what it watches,
how it groups, how it investigates, when it escalates. Settings that describe
how to *reach* an external platform — endpoints, sites, regions, hostnames,
credentials — SHALL NOT be read from `config.yaml`, and SHALL be resolved from
the environment only. A config file is therefore portable across deployments
of the same behavior, and carries nothing that changes when the same triage
behavior points at a different account or region.

#### Scenario: Connection setting present in the config file
- **WHEN** `config.yaml` contains keys describing a platform endpoint, site,
  or credential
- **THEN** the system does not use them to reach the platform, and resolves
  those settings from the environment as if the keys were absent

#### Scenario: Behavior setting present in the config file
- **WHEN** `config.yaml` contains a setting describing how the system behaves
- **THEN** the system resolves it normally, subject to the existing
  environment-wins precedence

### Requirement: Platform connection settings come from the environment
The system SHALL resolve the Datadog site and API credentials from the
environment only, using the platform's own conventional variable names rather
than the `section.key` mapping used for behavior settings. The site SHALL fall
back to a documented default when unset, so a deployment against the default
Datadog region need set only credentials. Credentials have no default and
SHALL be reported as required when absent.

#### Scenario: Site left unset
- **WHEN** the Datadog site environment variable is not set
- **THEN** the system resolves the site to the documented default

#### Scenario: Site set for a different region
- **WHEN** the Datadog site environment variable names a non-default region
- **THEN** the system reaches the platform at that region

#### Scenario: Credentials present in the environment
- **WHEN** the Datadog API credential environment variables are set
- **THEN** the system uses them to authenticate against the platform

#### Scenario: Credentials missing entirely
- **WHEN** the Datadog API credential environment variables are not set
- **THEN** the system reports that the credentials are required, rather than
  attempting an unauthenticated call

### Requirement: Ingestion lookback window
How far back a run looks for alerts is a behavior setting: it describes the
span of activity the system triages, and is tuned to the schedule the job runs
on. The system SHALL resolve it from `config.yaml` or the environment under
the usual precedence, applying a documented default when absent.

#### Scenario: Lookback omitted from configuration
- **WHEN** neither `config.yaml` nor the environment sets the ingestion
  lookback
- **THEN** the system resolves it to the documented default

#### Scenario: Lookback set by the operator
- **WHEN** the operator sets the ingestion lookback
- **THEN** a run considers only alerts that fired within that period, ending
  at the time the run starts

### Requirement: Ingestion request bounds are its own settings
The per-request timeout and retry bound that alert fetching runs under SHALL
be settings belonging to ingestion, resolved independently of the circuit
breaker values that bound investigation. Changing an investigation breaker
SHALL NOT change how alert fetching behaves, and the reverse SHALL also hold.
Each SHALL apply a documented default when absent.

#### Scenario: Ingestion bounds omitted from configuration
- **WHEN** neither `config.yaml` nor the environment sets the ingestion
  request timeout or retry bound
- **THEN** the system resolves each to its documented default

#### Scenario: An investigation breaker is changed
- **WHEN** the operator changes a circuit breaker value that bounds
  investigation
- **THEN** the timeout and retry bound applied to alert fetching are unchanged

#### Scenario: An ingestion bound is changed
- **WHEN** the operator changes the ingestion request timeout or retry bound
- **THEN** the circuit breaker values that bound investigation are unchanged

### Requirement: Re-notify cooldown
How long the system waits before reporting a still-firing incident again is a
behavior setting: it describes how noisy triage is allowed to be, and an
operator tunes it against how their team reads reports. The system SHALL
resolve it from `config.yaml` or the environment under the usual precedence,
applying the documented default when absent.

#### Scenario: Cooldown omitted from configuration
- **WHEN** neither `config.yaml` nor the environment sets the re-notify
  cooldown
- **THEN** the system resolves it to the documented default

#### Scenario: Cooldown set in the config file
- **WHEN** `config.yaml` sets the re-notify cooldown and no corresponding
  environment variable is set
- **THEN** the system resolves it to the value from `config.yaml`

#### Scenario: Cooldown overridden by the environment
- **WHEN** `config.yaml` sets the re-notify cooldown and the corresponding
  environment variable is set to a different value
- **THEN** the system resolves it to the environment variable's value,
  following the same precedence rule as every other behavior setting

### Requirement: Ledger retention period
How long a closed incident is kept for a human to consult is a behavior
setting: it describes how much triage history the system holds, and an
operator tunes it against how far back their team ever looks. The system SHALL
resolve it from `config.yaml` or the environment under the usual precedence,
applying the documented default when absent. It SHALL be resolved
independently of the re-notify cooldown: neither value SHALL be derived from
the other, so that history depth and report frequency are tuned separately.

#### Scenario: Retention omitted from configuration
- **WHEN** neither `config.yaml` nor the environment sets the ledger retention
  period
- **THEN** the system resolves it to the documented default

#### Scenario: Retention set by the operator
- **WHEN** the operator sets the ledger retention period in `config.yaml` or
  the environment, with the environment winning when both are set
- **THEN** the system keeps closed incidents for that period

#### Scenario: The cooldown is changed
- **WHEN** the operator changes the re-notify cooldown
- **THEN** the resolved retention period is unchanged, and changing the
  retention period likewise leaves the resolved cooldown unchanged

### Requirement: Ledger storage location comes from the environment
Where the triage ledger keeps its records is a deployment fact, not triage
behavior: it changes when the same behavior runs from a developer's machine, a
container, or a scheduled job, while what the system watches and how it groups
stay identical. The system SHALL resolve the ledger's storage location from the
environment only, and SHALL NOT read it from `config.yaml`. Unlike a
credential, it SHALL fall back to a documented default, so a manual run needs
no configuration at all.

#### Scenario: Storage location left unset
- **WHEN** the ledger storage environment variable is not set
- **THEN** the system uses the documented default location

#### Scenario: Storage location set for a deployment
- **WHEN** the ledger storage environment variable names a location
- **THEN** the system keeps its records there

#### Scenario: Storage location written into the config file
- **WHEN** `config.yaml` contains a key naming a ledger storage location
- **THEN** the system does not use it, and resolves the location from the
  environment as if the key were absent
