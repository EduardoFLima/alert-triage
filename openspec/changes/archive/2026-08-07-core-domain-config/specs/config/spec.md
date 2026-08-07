## Purpose

Defines the Config port and its YAML/environment-backed resolution rules,
including the mandatory `scope` value with no fallback, so every execution
context (manual, container, GKE/Cloud Run) can supply configuration
consistently without a schema rewrite.

## ADDED Requirements

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
The system SHALL require a `scope` value (v1: a single Datadog team) resolved
from `config.yaml`, an environment variable, or both. The system SHALL NOT
apply a default or "watch everything" fallback, and SHALL refuse to start if
`scope` cannot be resolved from either source.

#### Scenario: Scope provided only in config file
- **WHEN** `config.yaml` sets `scope.datadog_team` and no corresponding
  environment variable is set
- **THEN** the system starts using the value from `config.yaml`

#### Scenario: Scope provided only via environment variable
- **WHEN** no `config.yaml` exists (or it omits `scope`) and the
  `SCOPE_DATADOG_TEAM` environment variable is set
- **THEN** the system starts using the environment variable's value

#### Scenario: Scope missing from both sources
- **WHEN** `config.yaml` does not set `scope.datadog_team` and
  `SCOPE_DATADOG_TEAM` is not set
- **THEN** the system refuses to start and reports that `scope` is required

### Requirement: Environment variable overrides for any config value
The system SHALL allow any value normally set in `config.yaml` to instead be
set via an environment variable, using a predictable naming convention
mapping the section/key path to `SCREAMING_SNAKE_CASE`. When both a YAML
value and its corresponding environment variable are present, the
environment variable SHALL take precedence.

#### Scenario: Environment variable overrides YAML value
- **WHEN** `config.yaml` sets `scope.datadog_team` to one value and the
  `SCOPE_DATADOG_TEAM` environment variable is set to a different value
- **THEN** the system resolves `scope.datadog_team` to the environment
  variable's value

#### Scenario: Override applies beyond scope
- **WHEN** a non-scope config value (e.g. a circuit breaker threshold) is set
  in both `config.yaml` and its corresponding environment variable
- **THEN** the system resolves that value to the environment variable's
  value, following the same precedence rule as `scope`
