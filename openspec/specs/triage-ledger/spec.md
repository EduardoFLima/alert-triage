## Purpose

Gives a regrouped set of alerts continuity across runs: a stable incident
identity that survives new alerts joining it, a record of what has already been
reported, and the re-notify cooldown that decides whether a still-firing
incident is reported again or left alone.

## Requirements

### Requirement: Incidents carry a generated identity
The system SHALL assign each incident an identifier that is generated when the
incident is first opened, and SHALL NOT derive it from the incident's contents.
The identifier SHALL remain unchanged for the life of the incident, including
after further alerts are absorbed into it.

#### Scenario: Identity assigned when an incident opens
- **WHEN** a group of alerts is recognised as a new incident
- **THEN** the system assigns it an identifier that no other incident on record
  carries

#### Scenario: Identity survives the incident growing
- **WHEN** further alerts are absorbed into an incident already on record
- **THEN** the incident retains the identifier it was opened with

#### Scenario: Two incidents on one service are distinguishable
- **WHEN** the same service opens a second incident after an earlier one has
  gone quiet
- **THEN** the two incidents carry different identifiers and are tracked
  independently

### Requirement: Continuation of a known incident
The system SHALL treat a newly grouped set of alerts as a continuation of an
**open** incident already on record when it belongs to the same service **and**
either it shares an alert identifier with that incident, or its earliest alert
fell within the grouping time window of that incident's latest alert. A
continuation SHALL absorb the alerts that are not already recorded, extending
the incident's window, and SHALL NOT open a second incident.

#### Scenario: Overlapping ingestion windows re-deliver the same alerts
- **WHEN** a run groups alerts that were all already absorbed into an open
  incident on record
- **THEN** the system recognises the group as that incident and records no new
  alerts against it

#### Scenario: A firing incident produces new alerts
- **WHEN** a run groups alerts for a service that include an alert already
  recorded against an open incident, alongside alerts that are not
- **THEN** the system absorbs the new alerts into that incident and extends the
  window it spans

#### Scenario: A burst straddles two runs
- **WHEN** a run groups alerts for a service that share no alert identifier
  with any open incident, but whose earliest alert fell within the grouping
  window of an open incident's latest alert
- **THEN** the system treats them as a continuation of that incident, exactly
  as it would have grouped them had all the alerts arrived in one run

#### Scenario: A genuinely separate incident on the same service
- **WHEN** a run groups alerts for a service that share no alert identifier
  with any open incident and whose earliest alert fell further from every open
  incident's latest alert than the grouping window allows
- **THEN** the system opens a new incident with its own identifier

#### Scenario: Alerts for an unrecorded service
- **WHEN** a run groups alerts for a service with no open incident on record
- **THEN** the system opens a new incident

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

### Requirement: The cooldown is configurable with a documented default
The re-notify cooldown SHALL be an operator-configurable behavior setting,
resolved under the same precedence as every other configured value, and SHALL
fall back to a documented default when the operator sets nothing.

#### Scenario: Cooldown left unconfigured
- **WHEN** neither the config file nor the environment sets the re-notify
  cooldown
- **THEN** the system applies the documented default

#### Scenario: Cooldown set by the operator
- **WHEN** the operator sets the re-notify cooldown
- **THEN** the system suppresses repeat reports for that period instead of the
  default

### Requirement: Decisions are made against a supplied instant
The system SHALL evaluate the cooldown against an instant supplied to it rather
than reading a clock of its own, so that the decision is reproducible and
testable at any point in time.

#### Scenario: The same inputs at the same instant
- **WHEN** the cooldown decision is evaluated twice for the same incident and
  the same instant
- **THEN** the system reaches the same decision both times

#### Scenario: A controlled instant past the cooldown
- **WHEN** the decision is evaluated at an instant later than the cooldown
  allows, without any real time having passed
- **THEN** the system reports the incident

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

### Requirement: An incident closes once it can no longer affect a decision
The system SHALL treat an incident as closed once it can neither be continued
nor suppress a report — that is, once it has passed both the continuation
window and the re-notify cooldown. A closed incident SHALL take no part in any
subsequent decision: it SHALL NOT be continued by later alerts, and it SHALL
NOT suppress a later report. Closing is a change of standing, not a deletion —
the record remains available for a human to consult.

#### Scenario: A long-quiet incident closes
- **WHEN** an incident's latest alert is older than the grouping window and it
  was last reported longer ago than the cooldown
- **THEN** the system treats it as closed

#### Scenario: A quiet but recently reported incident stays open
- **WHEN** an incident's latest alert is older than the grouping window but the
  cooldown since its last report has not elapsed
- **THEN** the system keeps it open, so that a re-fire within the cooldown is
  still suppressed

#### Scenario: A closed incident is not continued
- **WHEN** alerts for a service arrive after that service's only incident has
  closed, and they would have continued it had it still been open
- **THEN** the system opens a new incident with a new identifier, and the
  closed incident is left as it stands

#### Scenario: A closed incident does not suppress a report
- **WHEN** a new incident opens on a service whose closed incident was reported
  more recently than the cooldown would allow
- **THEN** the system reports the new incident, because a closed incident's
  last report no longer suppresses anything

### Requirement: Closed incidents are retained for reference, then deleted
The system SHALL keep a closed incident in storage for a configurable retention
period, so that a human investigating after the fact can see what was reported,
when, and for which alerts. Once the retention period has elapsed since the
incident closed, the system SHALL delete it, so storage does not grow without
bound as runs accumulate. The retention period SHALL fall back to a documented
default of thirty days when the operator sets nothing, and SHALL be independent
of the cooldown — lengthening how long history is kept SHALL NOT change how
often an incident is reported, and the reverse SHALL also hold.

#### Scenario: A recently closed incident is kept
- **WHEN** an incident closed less than the retention period ago
- **THEN** the system keeps its record, including its identifier, its alerts,
  and when it was last reported

#### Scenario: A long-closed incident is deleted
- **WHEN** an incident closed longer ago than the retention period
- **THEN** the system deletes it from storage

#### Scenario: Retained history does not affect triage
- **WHEN** alerts arrive for a service whose closed incident is still within
  its retention period
- **THEN** the system decides exactly as it would have decided had that record
  already been deleted

#### Scenario: Retention left unconfigured
- **WHEN** neither the config file nor the environment sets the retention
  period
- **THEN** the system retains closed incidents for the documented default of
  thirty days

#### Scenario: Retention and cooldown are tuned separately
- **WHEN** the operator changes the retention period
- **THEN** how long a report is suppressed for is unchanged, and changing the
  cooldown likewise leaves the retention period unchanged

### Requirement: A ledger failure is reported, never disguised
When the ledger cannot be read or written, the system SHALL raise a failure
that a caller can distinguish from "no incidents on record". It SHALL NOT
report an empty or partial set of incidents in place of an error, since doing
so would silently re-report every incident as new.

#### Scenario: Storage cannot be read
- **WHEN** retrieving the incidents on record fails
- **THEN** the system signals a ledger failure rather than returning no
  incidents

#### Scenario: Storage cannot be written
- **WHEN** recording an incident fails
- **THEN** the system signals a ledger failure rather than completing silently

#### Scenario: Nothing on record is not a failure
- **WHEN** storage is reachable and holds no incidents for a service
- **THEN** the system returns an empty result as a success
