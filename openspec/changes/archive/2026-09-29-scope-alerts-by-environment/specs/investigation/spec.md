## ADDED Requirements

### Requirement: An investigation is told the environment of its incident
An investigation's target SHALL state the environment its incident was
observed in, alongside the service, the window, how much fired, and whether
the service is critical. The fact SHALL cross the published contract as part
of the target, and the investigation SHALL NOT read configuration to learn it.

The environment SHALL reach the crew through the same description that
carries the service, and every specialist SHALL be instructed to confine its
queries to the service *and* the environment, so that evidence about one
environment is never drawn from another in which the same service runs.

A target MAY state no environment, so that a caller that knows nothing of
environments still builds a valid target. Where it states none, the
description SHALL say so rather than omit the line, and specialists SHALL
scope by service alone.

#### Scenario: The target carries the environment
- **WHEN** an incident observed by a run scoped to `prod` is investigated
- **THEN** the target states `prod`, and the description given to the agents
  names it

#### Scenario: Specialists stay inside the environment
- **WHEN** a specialist queries the platform about an incident whose target
  states `prod`
- **THEN** its query is confined to that service in `prod`, not to the service
  across every environment

#### Scenario: Environment is carried, not looked up
- **WHEN** an investigation runs
- **THEN** it reads the environment only from the target it was given

#### Scenario: A target with no environment
- **WHEN** a caller builds a target without an environment
- **THEN** the target is valid, and the description states that no
  environment was given

### Requirement: An address the system composes stays inside the environment
Where the system composes an evidence address from the investigation's target
rather than reproducing it from what a tool was called with, the address SHALL
carry the target's environment wherever the platform's address form can
express one, so that a reader is shown the environment the evidence concerns
and not every environment of the service at once.

An address reproduced from a retrieval SHALL NOT have the environment added
to it. It has to open what was actually retrieved; a query that ran without
the environment is shown as it ran, which is the honest account of what the
evidence rests on.

Where a composed address form cannot express an environment, the address
SHALL still be given without it, since the service over the window is still
the right page.

#### Scenario: A composed service page carries the environment
- **WHEN** a finding's evidence is addressed as the service's own page,
  composed from a target stating `prod`
- **THEN** the address opens that page scoped to `prod`

#### Scenario: A retrieved query is not rewritten
- **WHEN** a retrieval's address is reproduced from the query the specialist
  ran, and that query named no environment
- **THEN** the address carries the query as it ran, without an environment
  added

#### Scenario: A target with no environment
- **WHEN** an address is composed from a target stating no environment
- **THEN** the address is composed without one, exactly as before this
  requirement
