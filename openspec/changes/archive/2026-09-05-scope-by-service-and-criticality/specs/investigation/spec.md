## ADDED Requirements

### Requirement: An investigation is told whether its service is critical
An investigation's target SHALL state whether the service it concerns was
declared critical, so that the crew reasons about the incident with the
urgency the deployment asked for. The fact SHALL cross the published contract
as part of the target, alongside the service, the window, and how much fired —
not as a separate call, and not by the investigation reading configuration of
its own.

A target SHALL default to not critical, so that a caller that knows nothing of
criticality still builds a valid target and every existing caller keeps
working unchanged.

The fact SHALL reach both the reasoning and the wording from one place: the
same description handed to the agents deciding what to consult is the one the
report's writer receives.

#### Scenario: A critical service's incident is stated as critical
- **WHEN** an incident on a service declared critical is investigated
- **THEN** the target states it is critical, and the description given to the
  agents says so

#### Scenario: A service not declared critical is stated plainly
- **WHEN** an incident on a service that is in scope and not declared critical
  is investigated
- **THEN** the target states it is not critical

#### Scenario: Criticality is carried, not looked up
- **WHEN** an investigation runs
- **THEN** it reads criticality only from the target it was given, and
  consults no configuration to determine it

#### Scenario: The report reflects the urgency
- **WHEN** an incident on a critical service is reported
- **THEN** the written account identifies the service as critical

#### Scenario: Criticality does not change what is gathered
- **WHEN** two incidents differing only in criticality are investigated
- **THEN** the same specialists are available to both, under the same bounds,
  and criticality alters how the incident is characterised rather than what
  evidence may be gathered
