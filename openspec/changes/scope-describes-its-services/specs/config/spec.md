## MODIFIED Requirements

### Requirement: Mandatory scope with no fallback
The system SHALL require a `scope` naming what is watched, resolved from
`config.yaml`, the environment, or both. `scope` is named by an owner
(`scope.owner`, from `SCOPE_OWNER`), by the services it watches
(`scope.services`, from `SCOPE_SERVICES`), or by both — they narrow along
different axes and compose rather than compete: an owner alone watches
everything that owner owns, services alone watch those services whoever owns
them, and both together watch the named services of that owner.

The system SHALL refuse to start when neither resolves. There is no default and
no "watch everything" fallback: a run that was told nothing about what to watch
has been told nothing worth guessing at, and guessing means triaging an
organisation's entire alert volume on somebody's behalf.

Both settings SHALL be named in platform-neutral terms, so that an alert source
for a different observability platform supplies them without the name lying
about where the value came from; translating either into a platform's own query
vocabulary is the alert source adapter's responsibility, not the config's.

#### Scenario: Scope provided only in config file
- **WHEN** `config.yaml` sets `scope.owner` and no corresponding environment
  variable is set
- **THEN** the system starts using the value from `config.yaml`

#### Scenario: Scope provided only via environment variable
- **WHEN** no `config.yaml` exists (or it omits `scope`) and the `SCOPE_OWNER`
  environment variable is set
- **THEN** the system starts using the environment variable's value

#### Scenario: Scope named by its services alone
- **WHEN** `scope` names one or more services and no owner
- **THEN** the system starts and watches those services, whoever owns them

#### Scenario: Scope named by both
- **WHEN** `scope` names an owner and one or more services
- **THEN** the system watches the named services of that owner, and an alert
  that fails either test is not watched

#### Scenario: Scope missing from both sources
- **WHEN** neither an owner nor any service resolves, from `config.yaml` or
  from the environment
- **THEN** the system refuses to start and reports that `scope` is required,
  naming both of the ways it may be given

#### Scenario: Owner is expressed in the platform's terms by the adapter
- **WHEN** the resolved owner is used to fetch alerts from an observability
  platform
- **THEN** the adapter translates it into that platform's own way of
  expressing ownership, and the config exposes no platform-specific form

## ADDED Requirements

### Requirement: Scope may name the services it watches
`scope` MAY carry a list of the services the job watches. Each entry SHALL name
a service; an entry naming none SHALL be refused at startup, since there is
nothing for its settings to describe. Every other key within an entry is
optional.

When the list is absent or empty, the system SHALL watch every service the
owner owns, which is the behavior of an owner-only scope and remains the
default. When the list names one or more services, the system SHALL watch those
services alone: an alert for any service not named SHALL NOT be triaged,
reported, or recorded, whoever owns it.

The list SHALL be able to name the scope by itself. Where it does and no owner
is resolved, the services alone decide what is watched — a deployment that
knows which services it cares about should not have to name an owner it does
not use to say so.

Which services are watched SHALL be resolvable from the environment as well as
from the file, because narrowing scope is exactly the kind of value that
differs between deployments of the same behavior. The environment SHALL be able
to name the services, replacing the file's list rather than adding to it, and
SHALL be able to adjust an individual named service's settings under the same
`section.key` mapping every other value follows. A service the environment
names but the file does not describe SHALL resolve to an entry with no settings
beyond its name.

#### Scenario: No services named
- **WHEN** `scope` names an owner and no services
- **THEN** the system watches every service that owner owns

#### Scenario: Services named and no owner
- **WHEN** `scope` names services and no owner
- **THEN** the system watches those services, whoever owns them, rather than
  refusing to start for want of an owner

#### Scenario: The list narrows what is watched
- **WHEN** `scope` names two services and the owner also owns a third
- **THEN** a run triages alerts for the two named services and none for the
  third

#### Scenario: An entry with no name
- **WHEN** a `scope.services` entry carries settings but names no service
- **THEN** the system refuses to start, naming the entry that has no service

#### Scenario: An entry with a name alone
- **WHEN** a `scope.services` entry names a service and sets nothing else
- **THEN** the service is watched, with no acceptable latency and not critical

#### Scenario: The environment names the services
- **WHEN** the environment names the services in scope and `config.yaml` names
  a different set
- **THEN** the system watches the services the environment named, as the
  environment wins for every other value

#### Scenario: The environment adjusts one declared service
- **WHEN** `config.yaml` describes a service and the environment sets one of
  that service's keys
- **THEN** the resolved service carries the environment's value for that key
  and the file's values for the rest

### Requirement: A watched service may declare the latency it accepts
An entry under `scope.services` MAY declare the latency that service is
expected to operate within. The value SHALL be optional and SHALL have no
default: a service that declares none accepts no particular latency, and
nothing about it is ever judged against a threshold. The system SHALL NOT
invent a default acceptable latency for a service, and SHALL NOT apply one
service's declared value to another.

#### Scenario: A service declares an acceptable latency
- **WHEN** a watched service declares an acceptable latency
- **THEN** the system resolves that value for that service

#### Scenario: A service declares none
- **WHEN** a watched service declares no acceptable latency
- **THEN** the system resolves no threshold for it, rather than a default one

#### Scenario: One service's threshold is its own
- **WHEN** one watched service declares an acceptable latency and another does
  not
- **THEN** the second service has no threshold, and the first service's value
  is not applied to it

### Requirement: A watched service may be declared critical
An entry under `scope.services` MAY declare the service critical. The flag
SHALL be optional and SHALL default to not critical, so a service is ordinary
unless an operator says otherwise. The system SHALL NOT infer criticality from
anything else — not from the presence of a threshold, not from alert volume,
and not from a service's name.

#### Scenario: A service is declared critical
- **WHEN** a watched service is declared critical
- **THEN** the system resolves it as critical

#### Scenario: A service says nothing about criticality
- **WHEN** a watched service is declared with no criticality
- **THEN** the system resolves it as not critical

#### Scenario: Criticality is never inferred
- **WHEN** a watched service declares an acceptable latency and no criticality
- **THEN** the system resolves it as not critical, because a threshold says
  nothing about how urgent the service is

## REMOVED Requirements

### Requirement: Optional critical_services section
**Reason**: A service is now described in exactly one place, `scope.services`,
which carries the criticality flag this section existed for. Two sections
describing the same service is the duplication the reformulation removes.

**Migration**: Move each entry under `critical_services` into the
`scope.services` list, naming the service and setting `critical: true`. Note
that listing services under `scope` also narrows what is watched, which
`critical_services` never did — a deployment that wants to keep watching every
service its owner owns should leave `scope.services` absent, or list every
service it watches rather than only the critical ones.

### Requirement: Threshold defaults within a declared critical service
**Reason**: The section that carried these thresholds is removed, and its one
threshold, `latency_threshold_ms`, named a figure the system could never
evaluate: no alert carried a latency, and the escalation rule it fed was meant
to fire before the investigation that alone could have measured one. Its
replacement, `acceptable_latency_ms` on a `scope.services` entry, is
deliberately without a default rather than with one — a latency no operator
stated is a latency nobody has judged, and silencing an incident against a
number the system chose for itself is the one thing this threshold must never
do.

**Migration**: Replace `critical_services.<service>.latency_threshold_ms` with
`acceptable_latency_ms` on that service's `scope.services` entry, and state it
explicitly: it no longer falls back to a default. `tier` has no replacement —
`critical` is a flag rather than a ranking.
