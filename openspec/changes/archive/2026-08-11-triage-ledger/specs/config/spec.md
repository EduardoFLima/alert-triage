## ADDED Requirements

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
