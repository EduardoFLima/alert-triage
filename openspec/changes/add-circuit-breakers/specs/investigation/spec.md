## MODIFIED Requirements

### Requirement: An investigation makes a bounded number of specialist consultations
The system SHALL bound how many specialist consultations one investigation may
make in total, counting every consultation rather than every specialist, and
SHALL refuse a consultation beyond that bound in terms the reasoning cannot read
as a specialist that found nothing.

A consultation is one hop: the reasoning reaching out to a specialist and that
specialist reporting back. The bound SHALL therefore be the operator-configurable
`max_agent_hops`, with a documented default of eight, and SHALL apply whether or
not the operator sets it — an unconfigured deployment is bounded by the default,
never unbounded.

The bound SHALL exceed the number of specialists declared, so that an incident
needing every signal can have every signal and still have questions left for the
ones whose answers raised more. A bound that admitted each specialist exactly
once would forbid the second question rather than bound it. A configured value
that does not exceed the declared crew SHALL still be honoured — an operator
narrowing the budget deliberately is not an error — but the default SHALL NOT be
one.

The reasoning SHALL be told the budget it has, and the number it is told SHALL
be the number that is enforced. The two SHALL read one value that neither the
instruction nor the enforcement owns, so that a configured budget cannot leave
the reasoning planning against a different one.

A refused consultation SHALL be recorded, and an investigation that hit the
bound SHALL be reported as one that could not consult everything it wanted
rather than as one that chose not to. The investigation SHALL still conclude on
what it gathered before the refusal, because the findings already in hand are no
less true for the budget having run out.

#### Scenario: A manager that will not stop
- **WHEN** the reasoning keeps consulting specialists past the bound
- **THEN** the further consultations are refused, the refusals are recorded,
  and the investigation concludes on what it already has

#### Scenario: A refusal is not a quiet specialist
- **WHEN** a consultation is refused for hitting the bound
- **THEN** what the reasoning is given back states that the consultation did
  not happen, and cannot be read as a specialist that reported nothing

#### Scenario: Every signal is still reachable
- **WHEN** an incident genuinely needs every declared specialist
- **THEN** every one of them can be consulted without hitting the bound

#### Scenario: Room for a second question
- **WHEN** every declared specialist has been consulted once
- **THEN** consultations remain for the follow-up questions their answers raised

#### Scenario: The operator narrows the budget
- **WHEN** a deployment configures a consultation bound lower than the default
- **THEN** consultations beyond that configured number are refused, and the
  refusals are recorded as they are for the default

#### Scenario: An unconfigured deployment is still bounded
- **WHEN** a deployment configures no consultation bound at all
- **THEN** the documented default bounds the investigation, rather than the
  investigation being unbounded

#### Scenario: The reasoning is told what is enforced
- **WHEN** a deployment configures a consultation bound
- **THEN** the budget stated to the reasoning is that configured number, not a
  different one stated elsewhere

## ADDED Requirements

### Requirement: A specialist's own tool calls are bounded
The system SHALL bound how many tool calls one specialist may make while
investigating one incident, counting every call it makes across every
consultation of it within that investigation. The bound SHALL be the
operator-configurable `max_tool_calls_per_agent`, with a documented default of
twelve, and SHALL apply whether or not the operator sets it.

The bound SHALL be enforced by declining the call rather than by counting after
it, so that a specialist that would loop is stopped before it spends the call
rather than found to have spent it.

A declined call SHALL be answered in terms the specialist cannot read as a
platform that returned nothing, for the reason a failed retrieval is: a bound
that reads as an empty result is how "we stopped looking" becomes "there was
nothing to find". The specialist SHALL still report on what it did retrieve
before the bound, and the investigation SHALL record that it was reached.

This bound is separate from the consultation bound above and SHALL be resolved
independently of it: how many searches one specialist may run and how many
specialists one incident may cost are different questions.

#### Scenario: A specialist that keeps searching
- **WHEN** a specialist makes tool calls past its bound during one investigation
- **THEN** the further calls are declined, and the specialist reports on the
  evidence it gathered before the bound

#### Scenario: A declined call is not an empty platform
- **WHEN** a tool call is declined for hitting the bound
- **THEN** what the specialist is given back states that the call did not
  happen, and cannot be read as a platform that returned no results

#### Scenario: The bound spans a specialist's consultations
- **WHEN** the same specialist is consulted twice in one investigation
- **THEN** the calls it made in the first consultation count against the calls
  it may make in the second

#### Scenario: One specialist's bound does not spend another's
- **WHEN** one specialist reaches its tool-call bound
- **THEN** every other specialist may still make its own full number of calls

#### Scenario: A bound investigation says so
- **WHEN** a specialist's tool-call bound is reached during an investigation
- **THEN** the investigation records it and is reported as incomplete rather
  than as one that looked everywhere

### Requirement: An investigation is bounded in wall-clock time
The system SHALL bound how long one investigation may run, by the
operator-configurable `max_investigation_duration_seconds`, with a documented
default of three hundred seconds, applied whether or not the operator sets it.

The bound SHALL be enforced in two stages, because a reasoning that is merely
running long and one that has stopped responding need different answers:

- Once the bound has elapsed, further tool calls SHALL be declined, so that the
  reasoning stops gathering and concludes on what it holds. What it is given
  back SHALL state that the call did not happen and SHALL NOT be readable as an
  empty result.
- An investigation that has not returned regardless SHALL be stopped, and
  everything gathered before it was stopped SHALL be kept rather than discarded
  with the run.

Either stage tripping SHALL be recorded, and the investigation SHALL be reported
as one that ran out of time rather than one that finished looking.

#### Scenario: An investigation running long stops gathering
- **WHEN** the duration bound elapses while the reasoning is still consulting
- **THEN** further calls are declined and the reasoning concludes on what it
  has already gathered

#### Scenario: An investigation that stops responding is stopped
- **WHEN** the duration bound elapses and the investigation does not return
- **THEN** it is stopped, and the findings gathered before it was stopped are
  kept

#### Scenario: Time is not a quiet platform
- **WHEN** a call is declined because the duration bound elapsed
- **THEN** what is given back states that the call did not happen, and cannot
  be read as a signal that had nothing in it

#### Scenario: An investigation inside its bound is unaffected
- **WHEN** an investigation completes within the duration bound
- **THEN** nothing is declined, nothing is recorded about time, and its findings
  carry no incompleteness from it

### Requirement: A tripped breaker is an incomplete investigation, not a failed one
An investigation in which a breaker tripped and which still produced findings
SHALL return those findings marked as gathered incompletely, on the same footing
as an investigation whose retrieval partly failed. It SHALL complete, its report
SHALL be delivered, and it SHALL NOT spend one of the incident's attempts — the
findings in hand are no less true for the bound having been reached, and an
incomplete automated triage is itself a reason a human should look sooner.

The report SHALL say which bound was reached, so that a reader can tell an
investigation that looked everywhere and found little from one that was stopped
before it could look.

An investigation in which a breaker tripped and which produced no findings at
all SHALL be treated as one that did not complete: no report SHALL be delivered
about the incident on the strength of it, and the incident SHALL be investigated
again while attempts remain. "We ran out of budget and learned nothing" is not
worth a message while there is still an attempt left to learn something.

#### Scenario: A trip with findings is reported
- **WHEN** a breaker trips in an investigation that has already produced
  findings
- **THEN** those findings are returned marked incomplete, the report is
  delivered, and no attempt is spent

#### Scenario: The report names the bound that was reached
- **WHEN** an investigation is reported after a breaker tripped
- **THEN** the report states which bound was reached, not merely that the
  investigation was incomplete

#### Scenario: A trip with nothing gathered is not reported
- **WHEN** a breaker trips before the investigation produced any finding
- **THEN** nothing is delivered about the incident, and it is investigated
  again on a later run while attempts remain

#### Scenario: A trip does not lose the incident
- **WHEN** any breaker trips
- **THEN** the incident is still recorded with its alerts absorbed and its
  identity unchanged
