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

The cooldown has one exception. When an incident was reported without findings
because its investigation did not complete, and a later retry within its
allotted attempts does produce findings, the system SHALL report it again
inside the cooldown, because the outcome the team was told has changed. Such a
report SHALL restart the cooldown like any other. A retry whose investigation
fails again SHALL NOT produce a report, since it changes nothing the team was
already told, and SHALL NOT restart the cooldown.

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

#### Scenario: A successful retry reports inside the cooldown
- **WHEN** an incident reported without findings is investigated again within
  its attempts and that investigation produces findings
- **THEN** the system reports it again despite the cooldown, and counts the
  cooldown afresh from that report

#### Scenario: A failed retry keeps the cooldown as it was
- **WHEN** a retry of an incident's investigation fails again
- **THEN** the system reports nothing and leaves the incident's last-reported
  instant unchanged

### Requirement: Recorded incidents survive the process
The system SHALL persist each incident it opens or continues — its identifier,
its service, the alerts absorbed into it, the window they span, when it was
last reported, and how many investigation attempts it has spent without
delivering findings — such that a later run in a new process reaches the same
decisions it would have reached had the runs shared a process.

#### Scenario: A second run in a new process
- **WHEN** an incident is recorded, the process ends, and a later run continues
  that incident from a fresh process
- **THEN** the system recognises the incident and applies its cooldown as
  recorded

#### Scenario: First run against empty storage
- **WHEN** a run consults storage that holds no incidents yet
- **THEN** the system reports no incidents on record and opens incidents
  normally, rather than treating the empty state as an error

#### Scenario: Alerts are recoverable from the record
- **WHEN** an incident is retrieved from storage
- **THEN** the alerts absorbed into it are recovered with the identity,
  timestamp, and provenance they carried when recorded

#### Scenario: Only open incidents are offered to a decision
- **WHEN** a run consults storage for a service that has both an open incident
  and a closed one still within its retention period
- **THEN** the system offers only the open incident to the decision, so
  retained history cannot influence it

#### Scenario: Spent attempts are recoverable from the record
- **WHEN** an incident whose investigation has failed is recorded, the process
  ends, and a later run retrieves it
- **THEN** the attempts already spent are recovered, so the incident gets the
  remaining attempts and no more

#### Scenario: An incident recorded before attempts were tracked
- **WHEN** a run retrieves an incident recorded by an earlier version of the
  system, which stored no attempt count for it
- **THEN** the system treats it as having no attempts outstanding, rather than
  failing to read the record
