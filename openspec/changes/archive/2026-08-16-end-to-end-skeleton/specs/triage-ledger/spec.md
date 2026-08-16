## MODIFIED Requirements

### Requirement: One report per incident until the cooldown elapses
The system SHALL report an incident when it is first opened, and SHALL suppress
any further report of that incident until the configured re-notify cooldown has
elapsed since it was last reported. Once the cooldown has elapsed and the
incident is still producing alerts, the system SHALL report it again and count
the cooldown afresh from that report. An incident SHALL count as reported only
once a report about it has actually been delivered: a report that was due and
could not be delivered SHALL leave the incident's last-reported instant
unchanged, so the cooldown never runs from a report nobody received.

#### Scenario: A newly opened incident
- **WHEN** an incident is opened
- **THEN** the system reports it

#### Scenario: A continuation within the cooldown
- **WHEN** an incident on record is continued and less than the cooldown has
  elapsed since it was last reported
- **THEN** the system suppresses the report, while still absorbing the new
  alerts into the incident

#### Scenario: A continuation after the cooldown
- **WHEN** an incident on record is continued and at least the cooldown has
  elapsed since it was last reported
- **THEN** the system reports it again

#### Scenario: The cooldown restarts on each report
- **WHEN** an incident is reported a second time and is continued again shortly
  afterwards
- **THEN** the system measures the cooldown from the second report, not the
  first, and suppresses the report

#### Scenario: Suppression is per incident, not per service
- **WHEN** one incident on a service is inside its cooldown and a separate
  incident opens on the same service
- **THEN** the system reports the new incident

#### Scenario: A due report that could not be delivered
- **WHEN** an incident is due to be reported and the report is not delivered
- **THEN** the incident's last-reported instant is left as it was, and the
  incident is due to be reported again at the next opportunity

#### Scenario: The decision and the stamp are separate
- **WHEN** the system decides an incident is due to be reported
- **THEN** the decision alone does not mark the incident as reported; the mark
  follows the delivery
