## ADDED Requirements

### Requirement: A manager decides which specialists an incident needs
The system SHALL decide, per incident, which specialists to consult, rather
than consulting every declared specialist on every incident. The decision SHALL
be made by reasoning over the incident and over what the specialists already
consulted reported, so that a specialist is chosen in the light of what the
previous one found rather than from a fixed order.

Every declared specialist SHALL be offered to that decision, so a specialist
added to the crew becomes available to be chosen without the deciding component
being edited. Which specialists were offered and which were consulted SHALL
both be observable from outside the investigation, so that the choice can be
examined rather than taken on trust.

A specialist MAY be consulted more than once, with a different question each
time: reading what came back and going back to the same specialist for the
detail it now knows to ask for is the reasoning this design exists to allow, not
a loop to be prevented. What bounds it is the budget below, on consultations as
a whole rather than per specialist.

Consulting a specialist SHALL NOT hand control away from the deciding
component: it reads what came back and decides what to do next.

#### Scenario: Only the signals an incident needs
- **WHEN** an incident's evidence is plainly confined to one or two signals
- **THEN** only the specialists for those signals are consulted, and the
  investigation completes without paying for the others

#### Scenario: A later choice follows an earlier answer
- **WHEN** the first specialist consulted reports something that points at
  another signal
- **THEN** the specialist for that signal is consulted next, rather than a
  fixed order being followed

#### Scenario: A specialist is asked a second question
- **WHEN** what a specialist reported raises a narrower question for that same
  specialist
- **THEN** it is consulted again with the new question, and both consultations
  contribute their findings

#### Scenario: Every specialist is available to be chosen
- **WHEN** a further specialist is added to the crew
- **THEN** it is offered to the decision on the next investigation, and the
  deciding component is unchanged

#### Scenario: The choice is observable
- **WHEN** an investigation completes
- **THEN** which specialists were offered and which were consulted can both be
  established from outside the investigation

### Requirement: An investigation records which signals it consulted
An investigation SHALL report which signals it consulted, alongside what it
found. A signal that no specialist was consulted about SHALL NOT be presented
as a signal that was examined and found clean, and the system SHALL NOT allow
one to be read as the other.

This SHALL hold whether or not anything was found: an investigation that
consulted two signals and found nothing has examined two signals, not all of
them.

#### Scenario: A signal nobody looked at
- **WHEN** an investigation consults the logs specialist and no other
- **THEN** what it returns names logs as the signal consulted, and does not
  present any other signal as clean

#### Scenario: Nothing found across the signals consulted
- **WHEN** an investigation consults two specialists and neither reports
  anything notable
- **THEN** what it returns says nothing notable was found in those two signals,
  naming them

#### Scenario: No specialist was consulted
- **WHEN** an investigation consults no specialist at all
- **THEN** what it returns names no signal as consulted, and is not presented
  as an investigation that looked and found nothing notable

### Requirement: An investigation concludes with a hypothesis and an explicit confidence level
An investigation SHALL produce a hypothesis about the incident together with an
explicit confidence level drawn from a fixed, declared set of levels. The
hypothesis SHALL be reasoned across the findings of every specialist consulted,
rather than restating one of them, and the confidence level SHALL be stated
rather than implied by the wording.

A hypothesis SHALL rest on findings that survived the evidence check. An
investigation left with no surviving findings SHALL report no hypothesis, and
SHALL NOT substitute a plausible one: a conclusion with nothing beneath it is
the verdict this system deliberately does not give.

A hypothesis SHALL remain a hypothesis. The system SHALL NOT present it as a
verdict, SHALL NOT recommend or take a remediating action, and SHALL NOT
suppress the findings and evidence it was drawn from, so that a reader can
disagree with the conclusion while keeping what it was built on.

A confidence level outside the declared set SHALL NOT be reported. The
investigation SHALL either resolve it to a declared level or report no
confidence, and SHALL NOT invent a level the system has not defined.

#### Scenario: A hypothesis across signals
- **WHEN** two specialists report findings that together suggest one
  explanation
- **THEN** the investigation returns a hypothesis reasoned across both, with a
  confidence level from the declared set

#### Scenario: Nothing to conclude from
- **WHEN** every finding an investigation produced was discarded by the
  evidence check
- **THEN** the investigation returns no hypothesis, rather than one formed
  without evidence

#### Scenario: The evidence outlives the conclusion
- **WHEN** an investigation returns a hypothesis
- **THEN** the findings and the evidence behind them are returned with it, so a
  reader can check the conclusion against them

#### Scenario: A confidence level nobody declared
- **WHEN** the reasoning states a confidence level outside the declared set
- **THEN** the investigation reports no confidence rather than that level

#### Scenario: A hypothesis is not an instruction
- **WHEN** an investigation returns a hypothesis
- **THEN** it recommends no action and takes none

### Requirement: The account of an investigation is written by an agent, and its evidence is not
The system SHALL produce the prose account a reader is given — a single-line
headline and the body explaining the hypothesis, what it rests on, and what is
worth checking — by reasoning separate from the reasoning that formed the
hypothesis, so that how well an investigation reasons and how well it is worded
can be changed apart from one another.

The evidence beneath that account SHALL be rendered from the retrieved items
themselves and SHALL NOT be produced by the reasoning that writes the account.
The account SHALL characterise the evidence; it SHALL NOT reproduce it. A
reader SHALL be given the retrieved items as they were retrieved, exactly as
they would have been without an agent writing anything.

The headline SHALL be a single line, so that a channel presenting it as a
subject or a heading can carry it unchanged.

When the account cannot be written — the reasoning fails, or returns something
unusable — the system SHALL fall back to an account it composes itself from the
hypothesis, the findings, and the evidence, and SHALL still deliver the report.
A report SHALL NOT be lost to a wording failure, because what it carries was
gathered before any of it was worded.

#### Scenario: The account is written separately from the conclusion
- **WHEN** the way the account is worded is changed
- **THEN** how the hypothesis is reasoned is unchanged, and the reverse holds

#### Scenario: Evidence is not written by the agent that words the report
- **WHEN** the account describes a pattern
- **THEN** the evidence shown beneath it is the retrieved items themselves, not
  the writing agent's rendering of them

#### Scenario: The headline is one line
- **WHEN** an account is produced
- **THEN** its headline is a single line a channel can present as a subject

#### Scenario: The wording fails
- **WHEN** the reasoning that writes the account fails or returns something
  unusable
- **THEN** the system composes the account itself and the report is still
  delivered, carrying the same hypothesis, findings, and evidence

### Requirement: An investigation makes a bounded number of specialist consultations
The system SHALL bound how many specialist consultations one investigation may
make in total, counting every consultation rather than every specialist, and
SHALL refuse a consultation beyond that bound in terms the reasoning cannot read
as a specialist that found nothing.

The bound SHALL exceed the number of specialists declared, so that an incident
needing every signal can have every signal and still have questions left for the
ones whose answers raised more. A bound that admitted each specialist exactly
once would forbid the second question rather than bound it.

A refused consultation SHALL be recorded, and an investigation that hit the
bound SHALL be reported as one that could not consult everything it wanted
rather than as one that chose not to. The investigation SHALL still conclude on
what it gathered before the refusal, because the findings already in hand are no
less true for the budget having run out.

This bound is not the operator-configurable breaker: it is what stops one
incident costing an unbounded number of model calls, and SHALL hold whether or
not a breaker is configured.

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

### Requirement: A finding is an observation with the evidence behind it
A finding SHALL be an observation about the incident, carrying the evidence it
rests on and naming the signal it came from. A finding SHALL NOT carry a
hypothesis, a root cause, a confidence level, or a recommended action: those
belong to the conclusion drawn across findings, and keeping them out of a
finding is what lets a reader tell what was observed from what was inferred.

A finding SHALL describe a pattern and illustrate it with a bounded number of
representative examples, together with how many times the pattern was seen. It
SHALL NOT carry every record behind the pattern, so that a report stays
readable however much the service logged.

A specialist that gathered evidence and found nothing notable SHALL return no
findings, which is a success and SHALL NOT be reported as a failure.

#### Scenario: Findings carry their evidence
- **WHEN** an investigation observes something about an incident
- **THEN** the observation is returned together with the evidence supporting it
  and the signal it was drawn from

#### Scenario: A pattern seen many times
- **WHEN** an investigation finds a pattern occurring hundreds of times
- **THEN** the finding reports how many times it occurred and carries only a
  bounded number of examples, not one entry per occurrence

#### Scenario: Nothing notable was found
- **WHEN** a specialist queries the platform successfully and finds nothing
  worth reporting
- **THEN** it returns no findings, and the investigation counts as successful

#### Scenario: A finding does not conclude
- **WHEN** findings are produced for any incident
- **THEN** each of them states what was observed and carries no hypothesis, no
  root cause, and no confidence level, which are reported once for the
  investigation rather than per finding

## MODIFIED Requirements

### Requirement: Specialist agents are added without changing their callers
The system SHALL express investigation as a set of specialist inquiries, each
scoped to one observability dimension, behind a single boundary the caller
depends on. Adding a specialist SHALL NOT change the caller, the shape of what
an investigation returns, or the way a report is built.

A caller SHALL learn which signals an investigation consulted, and SHALL NOT
learn how many specialists exist, in what order they were reached, or how a
consultation is driven. Which signals were consulted is what a report needs to
state its own scope honestly; everything else about the crew stays behind the
boundary.

What an investigation returns SHALL stay the same shape however many
specialists contributed to it, and each finding SHALL name the signal it came
from, so several specialists' work stays legible without the result changing
shape.

#### Scenario: One specialist today
- **WHEN** the system investigates an incident and consults the logs specialist
  alone
- **THEN** it returns findings from that specialist alone, in the same form a
  multi-specialist investigation returns, naming logs as the signal consulted

#### Scenario: A specialist is added
- **WHEN** a further specialist is introduced
- **THEN** the caller requesting an investigation is unchanged

#### Scenario: Findings from several specialists
- **WHEN** more than one specialist contributes findings to one investigation
- **THEN** each finding names the signal it was drawn from, and the result has
  the same shape a single specialist's would

#### Scenario: The crew stays behind the boundary
- **WHEN** a caller receives an investigation's result
- **THEN** it can tell which signals were consulted, and cannot tell how many
  specialists were declared or in what order they were reached

## REMOVED Requirements

### Requirement: An investigation returns findings, not a conclusion
**Reason**: This slice is the reversal it anticipated. An investigation now
concludes: it produces a hypothesis with an explicit confidence level, which
this requirement forbade on the grounds that nothing was entitled to state one.

**Migration**: Replaced by two requirements above. "A finding is an observation
with the evidence behind it" keeps everything still true of a *finding* — its
evidence, its signal, its bounded examples, and that finding nothing is a
success. "An investigation concludes with a hypothesis and an explicit
confidence level" states what an investigation as a whole may now say, and what
it may not say it on.
