## Purpose

Defines the Alert domain entity and the grouping logic that decides which
incoming alerts represent the same incident, so downstream investigation and
notification happen once per incident rather than once per alert.

## ADDED Requirements

### Requirement: Alert entity
The system SHALL represent an incoming alert as a domain entity carrying at
minimum a service tag and a timestamp, independent of any observability
platform's wire format.

#### Scenario: Alert constructed from raw fields
- **WHEN** an alert is created with a service tag and a timestamp
- **THEN** the resulting Alert entity exposes both values for use by grouping
  logic

### Requirement: Same-incident grouping
The system SHALL group two alerts into the same incident when they share the
same service tag and their timestamps fall within the same configured time
window.

#### Scenario: Alerts share service and window
- **WHEN** two alerts have the same service tag and their timestamps are
  within the grouping time window of each other
- **THEN** the system places them in the same group

#### Scenario: Alerts differ by service
- **WHEN** two alerts have different service tags
- **THEN** the system places them in different groups, regardless of timing

#### Scenario: Alerts fall outside the time window
- **WHEN** two alerts share the same service tag but their timestamps are
  further apart than the grouping time window
- **THEN** the system places them in different groups

### Requirement: One group, one investigation
The system SHALL treat each alert group as the unit that is investigated and
reported, not the individual alert.

#### Scenario: Multiple alerts in one group
- **WHEN** three alerts are grouped into a single incident
- **THEN** the system exposes exactly one group covering all three alerts to
  downstream processing, not three separate ones
