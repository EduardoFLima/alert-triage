## MODIFIED Requirements

### Requirement: Only alerts within the configured scope
The system SHALL return only the alerts a run's `scope` watches, and a scope
narrows along two axes that compose rather than compete.

Where `scope` names an owner, the system SHALL return only alerts belonging to
that owner; alerts belonging to any other owner SHALL NOT be returned. Where
`scope` names the services it watches, the system SHALL return only alerts for
those services; an alert for a service the scope does not name SHALL NOT be
returned, whoever owns it, so that narrowing the scope narrows what a run
fetches rather than only what it acts on. Where `scope` names both, an alert
SHALL satisfy both to be returned. Where it names only one, that one decides
alone — an owner-only scope returns every service that owner owns, and a
service-only scope returns those services whoever owns them.

The adapter SHALL translate the platform-neutral owner, and the
platform-neutral service names, into whatever that platform uses to express
each — the configuration exposes no platform-specific form of either.

#### Scenario: Alerts from another owner are excluded
- **WHEN** the scope names an owner and the platform holds recent alerts for
  that owner and for a different one
- **THEN** only the configured owner's alerts are returned

#### Scenario: Alerts for an unwatched service are excluded
- **WHEN** the scope names two services and the platform holds recent alerts of
  the configured owner for those two and for a third
- **THEN** only the alerts for the two named services are returned

#### Scenario: A scope naming no services keeps every one of them
- **WHEN** the scope names an owner and no services
- **THEN** every one of that owner's recent alerts is returned, whatever its
  service

#### Scenario: A scope naming no owner is not narrowed by ownership
- **WHEN** the scope names services and no owner
- **THEN** the alerts for those services are returned whoever owns them, and
  the request asks the platform for no owner in particular

## ADDED Requirements

### Requirement: An alert carries the latency that triggered it, where one was stated
Where the platform's account of an alert states the measured latency that
caused it to fire, the system SHALL populate the alert's observed latency from
that figure, normalised to a single documented unit so that two alerts stating
their latency differently are comparable.

Where no latency can be read, the alert SHALL carry none. The system SHALL NOT
substitute a zero, a default, or a figure taken from a measurement the account
does not identify as a latency — an alert about an error rate carries no
latency, and reading its figure as one would be worse than reading nothing. The
absence SHALL be distinguishable from a latency of zero, because a downstream
decision rests on whether a latency was read at all.

Reading the latency SHALL NOT be able to fail the fetch: an account the system
cannot make sense of yields an alert with no latency, alongside every other
alert retrieved.

#### Scenario: The platform states the latency
- **WHEN** the platform's account of an alert states the latency that triggered
  it
- **THEN** the resulting alert exposes that latency in the documented unit

#### Scenario: The latency is stated in another unit
- **WHEN** two alerts state their triggering latency in different units
- **THEN** both are exposed in the same documented unit, and comparing them
  compares the durations rather than the numbers as written

#### Scenario: The alert is not about latency
- **WHEN** an alert's account states a figure that is not a latency, such as an
  error count or a saturation percentage
- **THEN** the resulting alert carries no observed latency

#### Scenario: No figure at all
- **WHEN** an alert's account states no measurement
- **THEN** the resulting alert carries no observed latency, distinguishable
  from an alert whose latency was read as zero

#### Scenario: An unreadable account costs nothing else
- **WHEN** one alert's account cannot be made sense of and others can
- **THEN** every alert is still returned, the unreadable one carrying no
  observed latency, and the fetch does not fail
