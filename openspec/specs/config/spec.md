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

### Requirement: One resolved environment, read by everything
A run SHALL resolve its environment once, from the process environment
supplemented by an optional file beside the run, and every setting and
credential the run uses SHALL be read from that resolved environment. A name
the process exported SHALL win over the same name in the file, so a container
or scheduler is never overridden by a file lying beside it. No part of the
system SHALL read the process environment behind the resolved one: a name the
file supplies SHALL behave exactly as though it had been exported, including
where the setting is consumed by a vendor library rather than by this system's
own code.

#### Scenario: A value supplied only by the file
- **WHEN** a setting or credential is declared in the file and not exported by
  the process
- **THEN** the run behaves exactly as it would had the operator exported that
  name, whichever component consumes it

#### Scenario: The process disagrees with the file
- **WHEN** the same name is exported by the process and declared in the file
- **THEN** the run uses the exported value

#### Scenario: No file is present
- **WHEN** the file is absent
- **THEN** the run resolves entirely from the process environment and reports
  no error for the missing file

#### Scenario: A name the file only mentions
- **WHEN** the file names a variable without giving it a value
- **THEN** it does not shadow the same name exported by the process

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

### Requirement: Notification channel settings come from the environment
Where a report is sent and how to authenticate to get it there is a deployment
fact, not triage behavior: a mail server, a sender, a recipient list, and a
webhook URL all change when the same triage behavior runs for a different team
or from a different environment, while what the system watches and how it
groups stay identical. The system SHALL resolve every notification channel's
settings from the environment only, and SHALL NOT read them from `config.yaml`.
A channel setting written into `config.yaml` SHALL be inert, exactly as a
credential written there already is.

#### Scenario: Channel settings supplied by the environment
- **WHEN** the environment supplies a channel's settings
- **THEN** the system delivers reports through that channel using them

#### Scenario: Channel settings written into the config file
- **WHEN** `config.yaml` contains keys naming a mail server, a recipient, or a
  webhook URL
- **THEN** the system does not use them, and resolves the channel's settings
  from the environment as if the keys were absent

#### Scenario: A webhook URL is never a config file key
- **WHEN** an operator looks for a place to record a webhook URL
- **THEN** there is no `config.yaml` key for it, so a file shared between
  deployments cannot carry one deployment's destination

### Requirement: The environment decides which channels are active
The system SHALL treat a channel as active when the environment supplies the
settings that channel requires, and inactive when it does not. An inactive
channel SHALL take no part in delivery and SHALL NOT cause a failure by being
absent. A channel whose settings are supplied only in part SHALL be reported as
a configuration error rather than silently ignored, since a half-configured
channel is a mistake, not a decision.

#### Scenario: Only one channel configured
- **WHEN** the environment configures one channel and says nothing about the
  other
- **THEN** the system delivers through the configured channel alone, and the
  absence of the other is not an error

#### Scenario: Both channels configured
- **WHEN** the environment configures both channels
- **THEN** the system delivers through both

#### Scenario: A channel configured only in part
- **WHEN** the environment supplies some but not all of a channel's required
  settings
- **THEN** the system refuses to start, naming the missing setting

### Requirement: A deployment with no notification channel refuses to start
The system SHALL refuse to start when the environment configures no
notification channel at all. A run that can investigate but can tell nobody
what it found has no reason to run, and failing at startup makes that visible
immediately rather than at the moment a report was due.

#### Scenario: No channel configured
- **WHEN** the environment configures neither the email channel nor the Teams
  channel
- **THEN** the system refuses to start, saying that at least one notification
  channel must be configured

#### Scenario: The refusal is a configuration error like any other
- **WHEN** the system refuses to start for want of a channel
- **THEN** it fails the same way it fails for a missing mandatory scope or a
  missing credential, rather than in a manner particular to notification

### Requirement: Optional investigation section
The system SHALL treat the `investigation` section of `config.yaml` as
optional and SHALL apply documented defaults for every key it omits, so that a
run investigates without any configuration for it. The section SHALL carry
how an investigation reasons — the model it runs on — and how many attempts an
incident's investigation gets before the system stops retrying it, defaulting
to three. It SHALL NOT carry the location of, or credentials for, any platform
or model provider: those are deployment facts read from the environment only.
A key shaped like one written *into this section* SHALL be refused by name, as
any key the schema has never heard of already is — an operator who typed it
meant something by it, and silently ignoring it would leave them believing a
credential had been supplied. A credential written as its own top-level section
remains inert, exactly as it already is.

The attempt bound SHALL be resolved independently of the `circuit_breakers`
section, which bounds a single call inside one investigation rather than how
many investigations an incident is given.

#### Scenario: Config file omits investigation
- **WHEN** `config.yaml` is present but does not include an `investigation`
  section
- **THEN** the system resolves the investigation settings to their documented
  defaults and proceeds

#### Scenario: The operator chooses a model
- **WHEN** `config.yaml` sets the model under `investigation`
- **THEN** investigations run on that model rather than the default

#### Scenario: Attempts left unconfigured
- **WHEN** the operator sets no attempt bound for investigations
- **THEN** an incident's investigation is attempted up to three times in total

#### Scenario: The operator bounds the attempts
- **WHEN** `config.yaml` sets the attempt bound under `investigation`
- **THEN** an incident's investigation is attempted that many times rather
  than three

#### Scenario: The environment overrides the file
- **WHEN** `config.yaml` sets the model under `investigation` and the
  corresponding environment variable is also set
- **THEN** the environment variable's value wins, as it does for every other
  behavior setting

#### Scenario: A credential written into the section
- **WHEN** `config.yaml` sets a key shaped like a model or platform credential
  under `investigation`
- **THEN** the system refuses to start and names the unrecognised key, rather
  than starting as though a credential had been supplied
