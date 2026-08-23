## MODIFIED Requirements

### Requirement: Recorded incidents survive the process
The system SHALL persist each incident it opens or continues — its identifier,
its service, the alerts absorbed into it, the window they span, when it was
last reported, and how many investigation attempts it has spent without a
report being delivered — such that a later run in a new process reaches the
same decisions it would have reached had the runs shared a process.

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
- **THEN** the system treats it as having no attempts spent, rather than
  failing to read the record
