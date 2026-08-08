## Purpose

Defines the Alert domain entity and the grouping logic that decides which
incoming alerts represent the same incident, so downstream investigation and
notification happen once per incident rather than once per alert.

## Requirements

### Requirement: Alert entity
The system SHALL represent an incoming alert as a domain entity carrying at
minimum a service tag, a timestamp, a source identifier that is stable across
runs, the alert's title, and a link back to the alert in the platform that
reported it — independent of any observability platform's wire format.

#### Scenario: Alert constructed from raw fields
- **WHEN** an alert is created with a service tag and a timestamp
- **THEN** the resulting Alert entity exposes both values for use by grouping
  logic

#### Scenario: Alert carries identity and provenance
- **WHEN** an alert is created from a platform's report of it
- **THEN** the resulting Alert entity also exposes the source identifier,
  title, and link, so a downstream report can name which alerts fired and
  point a human at them

#### Scenario: Grouping ignores the added fields
- **WHEN** two alerts share a service tag and fall within the grouping window
  but differ in source identifier, title, and link
- **THEN** they are still placed in the same group — grouping reasons about
  the service tag and timestamp only

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
