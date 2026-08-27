## MODIFIED Requirements

### Requirement: The report a run sends
A run SHALL build each report from the incident and the findings of its
investigation. The report SHALL name the incident's service in its subject,
and its body SHALL carry both what the investigation found, with the evidence
behind it, and the alerts absorbed into the incident — when they fired, their
titles, and the links back to the platform that reported them.

Evidence in a report SHALL carry its own link back to the platform, where the
evidence has one, so that a reader who wants to see a finding for themselves
can go from the report to the thing it rests on. A link SHALL be rendered as
an address standing on its own, distinct from the text of what was retrieved,
so that a channel which turns addresses into links finds a whole one and a
channel which does not still shows a reader something they can copy. The
system SHALL NOT render a link inside a passage of text that is subject to
truncation, because a truncated address is worse than none: it still reads as
a link and leads somewhere the evidence is not.

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

#### Scenario: Evidence in a report can be followed
- **WHEN** a report is built from findings whose evidence carries links
- **THEN** each such piece of evidence appears with its link, and a reader can
  follow it to that evidence on the platform

#### Scenario: Evidence with no link is still reported
- **WHEN** a report is built from findings whose evidence carries no link
- **THEN** that evidence appears with its time and summary as before, and the
  report notes no absence

#### Scenario: A link is never truncated
- **WHEN** a piece of evidence carries a link and a long summary
- **THEN** the summary may be shortened and the link is rendered whole

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
