## MODIFIED Requirements

### Requirement: Alert entity
The system SHALL represent an incoming alert as a domain entity carrying at
minimum a service tag, a timestamp, a source identifier that is stable across
runs, the alert's title, a link back to the alert in the platform that
reported it, and the latency that triggered it where the platform stated one —
independent of any observability platform's wire format.

The observed latency SHALL be optional and SHALL be absent rather than zero
when none was stated, because "this fired at 40ms" and "nobody said how slow it
was" are opposite pieces of evidence and a later decision turns on which of
them holds.

#### Scenario: Alert constructed from raw fields
- **WHEN** an alert is created with a service tag and a timestamp
- **THEN** the resulting Alert entity exposes both values for use by grouping
  logic

#### Scenario: Alert carries identity and provenance
- **WHEN** an alert is created from a platform's report of it
- **THEN** the resulting Alert entity also exposes the source identifier,
  title, and link, so a downstream report can name which alerts fired and
  point a human at them

#### Scenario: Alert carries what it fired at
- **WHEN** an alert is created from a platform's report that stated the latency
  which triggered it
- **THEN** the resulting Alert entity exposes that latency

#### Scenario: An alert nobody measured
- **WHEN** an alert is created from a platform's report that stated no latency
- **THEN** the resulting Alert entity exposes no latency, which is
  distinguishable from one exposing a latency of zero

#### Scenario: Grouping ignores the added fields
- **WHEN** two alerts share a service tag and fall within the grouping window
  but differ in source identifier, title, link, and observed latency
- **THEN** they are still placed in the same group — grouping reasons about
  the service tag and timestamp only
