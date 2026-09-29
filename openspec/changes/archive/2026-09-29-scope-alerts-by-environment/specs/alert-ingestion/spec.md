## MODIFIED Requirements

### Requirement: Only alerts within the configured scope
The system SHALL return only alerts within the resolved `scope`, which is the
conjunction of three filters:

- an **owner** filter — only alerts belonging to that owner, applied only when
  it resolved;
- a **services** filter — only alerts belonging to one of the named services,
  applied only when it resolved;
- an **environment** filter — only alerts raised in the configured
  environment, always applied, since the environment always resolves.

Where owner and services both resolved, an alert SHALL satisfy both to be
returned: naming services narrows a run to those services rather than
widening it beyond the owner. Where one resolved, it alone decides between
them. At least one of the two always resolved, so the system SHALL NOT fetch
every alert of an environment unfiltered. The environment SHALL narrow
whichever of them applied, never widen it.

The adapter SHALL translate the platform-neutral owner, service and
environment names into whatever the platform uses to express ownership,
service membership and environment. The port SHALL NOT expose any filter in a
platform's own vocabulary.

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

#### Scenario: Alerts from another environment are excluded
- **WHEN** the scope's environment is `prod` and the platform holds recent
  alerts for an in-scope service in `prod` and in `staging`
- **THEN** only the `prod` alerts are returned

#### Scenario: The default environment applies without being set
- **WHEN** no environment was configured
- **THEN** only alerts raised in `prod` are returned

## ADDED Requirements

### Requirement: An alert's service view stays inside the environment
Where an alert's link addresses the platform's view of the alert's service
rather than the thing that raised it, that view SHALL be confined to the
scope's environment as well as to the service and the period, so that a
reader following it sees the alerts of the environment the run watches and
not those of every environment the service runs in.

A link addressing the thing that raised the alert SHALL be left as the
platform addresses it, because that page is the monitor's own and not a view
the system scopes.

#### Scenario: A service view is confined to the environment
- **WHEN** an alert raised in `prod` has no monitor to link to, so its link
  addresses the service's alerts over the period it fired in
- **THEN** that view is confined to `prod`

#### Scenario: A monitor link is not rewritten
- **WHEN** an alert names the monitor that raised it
- **THEN** its link addresses that monitor over the period it fired in, with
  no environment added
