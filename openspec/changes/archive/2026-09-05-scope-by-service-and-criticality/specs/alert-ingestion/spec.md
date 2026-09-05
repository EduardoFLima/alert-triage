## MODIFIED Requirements

### Requirement: Only alerts within the configured scope
The system SHALL return only alerts within the resolved `scope`, which is the
conjunction of two independent filters, each applied only when it resolved:

- an **owner** filter — only alerts belonging to that owner;
- a **services** filter — only alerts belonging to one of the named services.

Where both resolved, an alert SHALL satisfy both to be returned: naming
services narrows a run to those services rather than widening it beyond the
owner. Where one resolved, it alone decides. At least one always resolved, so
the system SHALL NOT fetch unfiltered.

The adapter SHALL translate the platform-neutral owner and service names into
whatever the platform uses to express ownership and service membership. The
port SHALL NOT expose either filter in a platform's own vocabulary.

Criticality SHALL have no effect here: a critical service is fetched on the
same terms as any other service in scope.

#### Scenario: Alerts from another owner are excluded
- **WHEN** the platform holds recent alerts for the configured scope owner and
  for a different owner
- **THEN** only the configured owner's alerts are returned

#### Scenario: Alerts from a service outside the named services are excluded
- **WHEN** `scope.services` names two services and the platform holds recent
  alerts for those and for a third
- **THEN** only alerts for the two named services are returned

#### Scenario: Both filters must be satisfied
- **WHEN** both an owner and services resolved, and the platform holds an
  alert for a named service owned by someone else
- **THEN** that alert is not returned

#### Scenario: A named service the owner does not own yields nothing
- **WHEN** both filters resolved and no alert satisfies both
- **THEN** no alerts are returned, and this is a valid empty result rather
  than a failure

#### Scenario: Services alone bound the fetch
- **WHEN** `scope.services` resolved and no owner did
- **THEN** alerts for the named services are returned regardless of who owns
  them

#### Scenario: A critical service is fetched like any other
- **WHEN** one service in scope is declared critical and another is not
- **THEN** alerts for both are returned on the same terms
