## ADDED Requirements

### Requirement: An investigation is told whether its target is a critical service
The target an investigation is asked about SHALL state whether the service is
one its operators declared critical, alongside the service, the window, and the
alert volume it already states. It is a fact about the service rather than
about the alerts, and it crosses the boundary as one — the investigation learns
that this service matters more to its owners, and learns nothing about
incidents, tiers, or the configuration that said so.

What the investigation may do with it is bounded. Criticality MAY inform how
thoroughly an incident is worked: which signals are worth consulting, and how
readily an investigation settles for one specialist's answer. It SHALL NOT
change what the evidence is taken to mean. In particular, an investigation
SHALL NOT report a higher confidence for a critical service than the same
evidence would earn for an ordinary one, and SHALL NOT state a hypothesis it
would not otherwise have stated. A service being important is a reason to look
harder, never a reason to be surer.

A target that says nothing about criticality SHALL be investigated exactly as
targets are today, so that adding this changes nothing for a deployment that
declares no service critical.

#### Scenario: The target states criticality
- **WHEN** an investigation is requested for an incident on a service declared
  critical
- **THEN** the target it is asked about states that the service is critical

#### Scenario: An ordinary service
- **WHEN** an investigation is requested for an incident on a service not
  declared critical
- **THEN** the target states that it is not, and the investigation proceeds as
  it does for any target

#### Scenario: Criticality does not inflate confidence
- **WHEN** the same evidence is gathered for an incident on a critical service
  and for one on an ordinary service
- **THEN** the confidence level attached to the resulting hypothesis is the
  same in both, because confidence is a statement about the evidence

#### Scenario: Criticality does not manufacture a hypothesis
- **WHEN** an investigation of a critical service gathers evidence supporting
  no conclusion
- **THEN** it produces no hypothesis, exactly as it would for an ordinary
  service, rather than offering one because the service matters

#### Scenario: The investigation learns nothing else about the caller
- **WHEN** an investigation is asked about a critical service
- **THEN** what it is told is that the service is critical, and not which
  configuration declared it, what tier it sits in, or what an incident is
