## ADDED Requirements

### Requirement: Scope may name the services it watches
`scope` MAY carry a list of the services the job watches. Each entry SHALL name
a service; an entry naming none SHALL be refused at startup, since there is
nothing for its settings to describe. Every other key within an entry is
optional.

When the list is absent or empty, the system SHALL watch every service the
owner owns, which is the behavior of an owner-only scope and remains the
default. When the list names one or more services, the system SHALL watch those
services alone: alerts the owner owns for any service not named SHALL NOT be
triaged, reported, or recorded.

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
