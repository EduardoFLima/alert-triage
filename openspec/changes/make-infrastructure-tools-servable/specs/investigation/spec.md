## ADDED Requirements

### Requirement: A specialist is offered only tools the model platform will serve
Every tool a specialist declares SHALL be one the model platform will accept
being offered. Where a platform refuses a tool — because of its schema, or for
any other reason it gives before the agent runs — the system SHALL NOT offer
that tool, and the specialist SHALL run with the tools that remain.

A refusal SHALL be treated as a fact about the deployment, in the same way a
toolset the deployment has not configured is: the specialist reports what it
could reach, and a signal it could not reach is an empty result rather than a
failed investigation. The system SHALL NOT allow one refused tool to stop a
specialist from being consulted at all.

Which tools a deployment's model platform will serve SHALL be established
against the real platform, not assumed. A specialist that cannot be served
SHALL be named by that check, so that a specialist silently returning nothing
in every report is not a state the system can be left in.

#### Scenario: A tool the platform refuses to serve
- **WHEN** the model platform refuses one of a specialist's tools before the
  agent runs
- **THEN** the specialist is consulted with its remaining tools, and reports
  what those could reach

#### Scenario: A specialist whose signal is now out of reach
- **WHEN** the tools a specialist needed for part of its signal were all
  refused
- **THEN** that part is reported as an empty result, and the investigation
  continues

#### Scenario: A specialist that cannot be served at all
- **WHEN** a specialist cannot be offered to the real model platform
- **THEN** the check against that platform fails naming the specialist, rather
  than the specialist returning nothing in every report
