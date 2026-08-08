## MODIFIED Requirements

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
