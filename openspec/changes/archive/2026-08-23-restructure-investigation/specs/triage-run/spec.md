## MODIFIED Requirements

### Requirement: The report a run sends
A run SHALL build each report from the incident and the findings of its
investigation. The report SHALL name the incident's service in its subject,
and its body SHALL carry both what the investigation found, with the evidence
behind it, and the alerts absorbed into the incident — when they fired, their
titles, and the links back to the platform that reported them.

When the investigation behind a report could not gather all the evidence it
asked for, the report SHALL say so, so that a reader can tell findings drawn
from everything the platform holds from findings drawn from part of it. A
report SHALL NOT present a partially evidenced investigation as a complete
one.

When no findings are available because every investigation of the incident
failed, the report SHALL carry the alerts as above and SHALL state plainly
that investigation was attempted and could not complete, rather than
presenting itself as triage. A report SHALL NOT present a hypothesis, a root
cause, or a confidence level, none of which an investigation produces yet.

#### Scenario: A report identifies its service and alerts
- **WHEN** a report is built for an incident with three alerts
- **THEN** its subject names the service and its body lists all three alerts
  with their times and links

#### Scenario: A report carries what was found
- **WHEN** an investigation returned findings for an incident
- **THEN** the report's body states those findings and the evidence behind
  them

#### Scenario: The report does not pretend to conclude
- **WHEN** a report is built from findings
- **THEN** its body presents observations and evidence, and offers no
  hypothesis, root cause, or confidence level

#### Scenario: The report does not pretend to be triage
- **WHEN** a report is built for an incident whose investigations all failed
- **THEN** its body says investigation was attempted and could not complete,
  rather than presenting itself as a triage conclusion

#### Scenario: The report does not pretend to be complete
- **WHEN** a report is built from findings whose investigation could not
  gather part of its evidence
- **THEN** its body says the evidence gathered was incomplete, alongside the
  findings it did produce

#### Scenario: A complete investigation reads as one
- **WHEN** a report is built from findings whose investigation gathered
  everything it asked for
- **THEN** its body carries no incompleteness note, whether or not the
  findings were notable

#### Scenario: Report content is replaceable
- **WHEN** the way a report's body is produced changes
- **THEN** neither the run's ordering nor any notification channel changes
  with it
