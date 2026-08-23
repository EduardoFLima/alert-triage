## ADDED Requirements

### Requirement: A specialist is a declaration that owns what it may ask
A specialist SHALL be declared as a whole: the signal it reports under, what
it is instructed to look for, the shape of what it reports, the tools it is
permitted to reach, and — where it differs from the default — the model it
reasons on. What a specialist is permitted to ask SHALL be part of that
declaration rather than an operator setting, because an instruction assumes
the tools it was written against and the two cannot be tuned apart.

Adding a specialist, or changing which tools an existing one may reach, SHALL
be an edit to that specialist's declaration alone, and SHALL NOT change the
component that runs the crew, the caller that requests an investigation, or
any other specialist. A specialist SHALL be able to reason on a different
model from its siblings without being a special case.

Deployment facts — where the platform is, how to authenticate, and the model
every specialist runs on unless it says otherwise — SHALL be supplied to a
declaration rather than written into it.

#### Scenario: A specialist's tools change
- **WHEN** the tools one specialist is permitted to reach are widened
- **THEN** only that specialist's declaration changes, and no other specialist
  and no caller changes with it

#### Scenario: A specialist reasons on its own model
- **WHEN** one specialist is configured to run on a different model from the
  default
- **THEN** it reasons on that model and every other specialist reasons on the
  default

#### Scenario: A specialist may not reach a tool it did not declare
- **WHEN** a specialist is run against a platform offering many tools
- **THEN** the tools available to it are the ones its declaration names, and no
  others

#### Scenario: Deployment facts are supplied, not declared
- **WHEN** the same specialist is run against a different platform account
- **THEN** its declaration is unchanged, and only what was supplied to it
  differs

### Requirement: A failed retrieval is never an absence of evidence
When a retrieval of evidence fails — the platform refuses it, is unreachable,
or answers with something that cannot be read — the system SHALL make the
failure explicit to whatever reasons over the result, in terms that cannot be
read as a successful retrieval that found nothing. "The service logged
nothing" and "the search failed" are opposite findings, and the system SHALL
NOT allow one to be presented as the other.

The system SHALL record every failed retrieval within an investigation,
separately from the evidence that was successfully gathered.

#### Scenario: A refused search
- **WHEN** a specialist's search is refused by the platform
- **THEN** what the specialist is given back states that the retrieval failed,
  and cannot be read as an empty result

#### Scenario: A quiet service and a broken search are distinguishable
- **WHEN** one investigation's retrieval returns no evidence and another's
  fails
- **THEN** the two outcomes are recorded distinctly, and the first is not
  reported as a failure nor the second as quiet

#### Scenario: Failures are recorded
- **WHEN** two of an investigation's retrievals fail and three succeed
- **THEN** the investigation records the two failures alongside the evidence
  the three returned

### Requirement: An investigation that could not gather all its evidence says so
An investigation in which at least one retrieval failed but which still
produced findings SHALL return those findings marked as gathered incompletely,
and the marking SHALL survive into the report. A reader SHALL be able to tell
an investigation that looked everywhere and found little from one that could
not look everywhere.

An investigation in which every retrieval failed SHALL be a failure, not an
empty result, however calmly the reasoning reported having found nothing.

#### Scenario: Some evidence could not be gathered
- **WHEN** an investigation's logs retrieval succeeds and its metrics
  retrieval fails, and findings are produced from the logs
- **THEN** the findings are returned, marked as gathered incompletely

#### Scenario: Nothing could be gathered
- **WHEN** every retrieval an investigation attempted failed
- **THEN** the investigation is reported as a failure rather than as an
  investigation that found nothing notable

#### Scenario: A complete investigation is not marked
- **WHEN** an investigation gathers all the evidence it asked for
- **THEN** its findings carry no incompleteness marking, whether or not they
  found anything notable

## MODIFIED Requirements

### Requirement: Specialist agents are added without changing their callers
The system SHALL express investigation as a set of specialist inquiries, each
scoped to one observability dimension, behind a single boundary the caller
depends on. Adding a specialist SHALL NOT change the caller, the shape of what
an investigation returns, or the way a report is built. A caller SHALL NOT be
able to observe how many specialists ran.

What an investigation returns SHALL stay the same shape however many
specialists contributed to it, and each finding SHALL name the signal it came
from, so several specialists' work stays legible without the result changing
shape.

#### Scenario: One specialist today
- **WHEN** the system investigates an incident with only the logs specialist
  available
- **THEN** it returns findings from that specialist alone, in the same form a
  multi-specialist investigation returns

#### Scenario: A specialist is added
- **WHEN** a further specialist is introduced
- **THEN** the caller requesting an investigation is unchanged

#### Scenario: Findings from several specialists
- **WHEN** more than one specialist contributes findings to one investigation
- **THEN** each finding names the signal it was drawn from, and the result has
  the same shape a single specialist's would

### Requirement: The logs specialist reports error and warning patterns
The logs specialist SHALL examine the incident's service over the incident's
window and report the error and warning patterns it finds — what recurs, at
what rate, and when it started relative to the alerts. It SHALL cite the log
evidence behind each observation, and SHALL NOT report a pattern it did not
observe in retrieved logs.

The specialist SHALL be instructed in the terms of the platform it queries,
including that platform's query dialect, because a query dialect is not
translatable between platforms. A second platform's logs specialist SHALL be a
declaration of its own rather than the same specialist pointed elsewhere.

#### Scenario: A recurring error is present
- **WHEN** the service logged the same error repeatedly during the incident's
  window
- **THEN** the findings name that pattern, how often it occurred, and when it
  began

#### Scenario: The logs are quiet
- **WHEN** the service logged nothing unusual during the incident's window
- **THEN** the findings say so rather than inventing a pattern

#### Scenario: Evidence is traceable
- **WHEN** the findings report a log pattern
- **THEN** a human reading the report can tell which logs it was drawn from

#### Scenario: Another platform's logs specialist
- **WHEN** a contributor adds a logs specialist for a different observability
  platform
- **THEN** they declare a specialist of their own, and the existing one is
  unchanged

### Requirement: Evidence in a finding is always evidence the platform returned
The evidence carried by a finding SHALL consist only of what the observability
platform actually returned during that investigation. The system SHALL NOT
present as evidence any text produced by the reasoning that formed the
finding, however plausible it looks. Evidence SHALL be identified against what
was retrieved and reproduced from the retrieved result, so that a fabricated
or mistaken reference cannot be rendered into a report.

Evidence SHALL be identifiable at two grains: the retrieval as a whole, and an
individual item within it. A finding about a pattern cites the items showing
it; a finding about something with no discrete items — an aggregate, a
dependency map, a waterfall — cites the retrieval. A finding citing neither
SHALL be discarded.

Every retrieved item SHALL be rendered into a report through one common
normalisation — an identifier, the instant it concerns, and a human-readable
summary alongside what the platform actually returned — rather than through a
translation written per tool, so that a specialist reaching a new tool needs
no new rendering.

A finding whose evidence cannot be traced back to what was retrieved SHALL be
discarded, and the system SHALL record that it was discarded and why, so that
fabrication is visible to whoever is tuning the investigation. Discarding one
finding SHALL NOT discard the others, and SHALL NOT fail the investigation:
findings whose evidence checks out SHALL still be reported. An investigation
left with no findings after discarding SHALL return an empty result — an
honest "nothing notable" — rather than a failure, because the investigation
did run.

This requirement constrains evidence, not description. How a finding
characterises its evidence — a rate, a count, a description of a pattern —
remains the investigation's own account of what it saw, which is why the
examples travel with it for a human to check it against.

#### Scenario: Evidence names something that was never retrieved
- **WHEN** a finding's evidence refers to a retrieval or an item the platform
  did not return during the investigation
- **THEN** the finding is discarded, the discard is recorded, and it does not
  appear in any report

#### Scenario: A finding about an aggregate
- **WHEN** a finding concerns a result with no discrete items in it
- **THEN** it cites the retrieval that produced it, and is kept

#### Scenario: A finding citing nothing
- **WHEN** a finding cites neither a retrieval nor an item within one
- **THEN** it is discarded

#### Scenario: One bad finding among good ones
- **WHEN** an investigation produces three findings and only one has evidence
  that cannot be traced to what was retrieved
- **THEN** the other two are returned and reported, and the investigation is
  not treated as a failure

#### Scenario: Nothing survives the check
- **WHEN** every finding an investigation produced has untraceable evidence
- **THEN** the investigation returns no findings, which is reported as nothing
  notable rather than as a failed investigation

#### Scenario: Evidence is reproduced, not restated
- **WHEN** a finding's evidence is presented to a human
- **THEN** what they read is the retrieved result itself, not a retelling of it

#### Scenario: Evidence from a tool nobody anticipated
- **WHEN** a specialist gathers evidence from a tool the system carries no
  per-tool handling for
- **THEN** that evidence is identified, checked, and rendered like any other

### Requirement: An investigation that cannot complete tells nobody
When an investigation cannot complete — the reasoning fails, no evidence could
be gathered at all, or the investigation errors for any other reason — the
system SHALL return no findings rather than partial ones presented as
complete, and SHALL make the failure and its reason available to its caller. It
SHALL NOT produce a report about the incident on the strength of a failed
investigation, because "these alerts fired and nothing could be learned about
them" is not worth a message while there is still an attempt left to learn
something.

An investigation that gathered some of its evidence and produced findings is
not a failed investigation: it completes, and reports itself as incomplete.

A failed investigation SHALL NOT prevent the incident from being recorded, and
SHALL NOT cause the incident's alerts to be lost or its identity to change.

#### Scenario: No evidence could be gathered
- **WHEN** an investigation could reach no evidence at all
- **THEN** it reports that it did not complete, naming the reason, and returns
  no findings

#### Scenario: A failed investigation is silent
- **WHEN** an investigation for an incident fails and attempts remain
- **THEN** nothing is delivered about that incident, and it is still recorded
  with its alerts absorbed

#### Scenario: Failure is distinguishable from a quiet result
- **WHEN** an investigation fails
- **THEN** the outcome is distinguishable from an investigation that
  succeeded and found nothing notable

#### Scenario: Partial evidence is not failure
- **WHEN** an investigation gathers part of the evidence it asked for and
  produces findings from it
- **THEN** it completes, its findings are returned, and no attempt is spent

## REMOVED Requirements

### Requirement: Evidence is gathered through a platform boundary
**Reason**: The boundary it describes was built in slice 6 and shown not to
hold. Checked against a real second platform rather than assumed: every
Grafana query tool takes a datasource discovered at runtime with no counterpart
here, Grafana has no service-dependency tool for the evidence this project
scopes into v1, and it has primitives a Datadog-shaped boundary cannot express.
The vocabulary was never neutral either — it was Datadog's, untested. The
promise that substituting a platform leaves every specialist unchanged is not
expensive to keep; against a real second platform it is false. The full
argument is in `docs/vision.md`, "Evidence and the platform boundary".

**Migration**: MCP is the boundary — it is already a cross-vendor protocol for
discovering and invoking tools. What stays platform-neutral is the machinery:
the evidence check, the output schemas, the signal, the finding, the report,
the retry arc, the ledger. What is platform-specific is the specialist itself,
covered by "A specialist is a declaration that owns what it may ask" and by
the logs specialist's requirement above. A contributor adding a platform
declares specialists of their own rather than implementing a boundary of ours,
and gets a working specialist from the first one rather than after the last.
