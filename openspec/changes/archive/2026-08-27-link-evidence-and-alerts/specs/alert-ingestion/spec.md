## MODIFIED Requirements

### Requirement: Translation of platform alerts into Alert entities
For each alert it retrieves, the system SHALL populate the `Alert` entity's
service tag from the alert's service tag, its timestamp from when the alert
fired, its source identifier from the platform's identifier for that alert,
its title from the alert's title, and its link from the platform's URL for
that alert.

An alert's link SHALL address a page the platform serves, built from an
identifier the platform supports addressing that page by. The system SHALL NOT
build a link by composing an identifier into a route the platform does not
document as accepting it, because such a link is indistinguishable from a
working one until a human follows it and arrives nowhere. Where the alert's
own identifier has no address form, the system SHALL link to the thing that
raised the alert, or to the platform's view of the alert's service over the
period it fired in, in preference to a link known not to open.

An alert's link SHALL carry the reader to what fired at the time it fired,
where the platform's address form allows a period to be expressed, so that a
reader following it days later sees the alert rather than the present.

#### Scenario: Platform alert is translated
- **WHEN** the platform returns an alert carrying a service tag, a fire time,
  an identifier, a title, and a URL
- **THEN** the resulting `Alert` exposes each of those values in the
  corresponding field

#### Scenario: Timestamps are timezone-aware
- **WHEN** an alert is translated from a platform timestamp
- **THEN** its `fired_at` is timezone-aware and expressed in UTC, so grouping
  compares alerts from any source consistently

#### Scenario: A translated alert's link opens
- **WHEN** a human follows the link on a translated alert
- **THEN** the platform serves them a page about that alert, rather than an
  error or an empty view

#### Scenario: The alert's own identifier has no address form
- **WHEN** the platform's identifier for an alert cannot be composed into a
  page address the platform serves
- **THEN** the alert's link addresses what raised it, or the platform's view of
  its service over the period it fired in, and never a route the platform does
  not accept that identifier for

#### Scenario: A link outlives the moment
- **WHEN** a human follows an alert's link some time after it fired
- **THEN** what they are shown covers when the alert fired rather than the
  present moment
