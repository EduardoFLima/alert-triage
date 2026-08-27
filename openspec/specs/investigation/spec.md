## Purpose

What the system does with an incident before it reports it: the evidence it
gathers around the alert window, what it is allowed to say about that
evidence, and what happens when the gathering cannot complete. Investigation
is the first-pass legwork a knowledgeable human would do, kept separate from
the conclusion drawn from it.

## Requirements

### Requirement: An investigation is asked about one incident
The system SHALL investigate an incident as a whole — its service, the alerts
absorbed into it, and the window they span — and SHALL NOT investigate alerts
individually. An investigation SHALL be requested only for an incident whose
report is due, so that a suppressed report costs no investigation.

#### Scenario: An incident is investigated once
- **WHEN** an incident with four alerts is due to be reported
- **THEN** one investigation is performed for the incident, not one per alert

#### Scenario: A suppressed report is not investigated
- **WHEN** an incident is continued inside its cooldown, so no report is due
- **THEN** no investigation is performed for it

#### Scenario: The window comes from the incident
- **WHEN** an incident is investigated
- **THEN** the evidence gathered concerns the period spanned by the
  incident's alerts, not a fixed period of the investigator's own choosing

### Requirement: An investigation returns findings, not a conclusion
An investigation SHALL return findings: observations about the incident, each
carrying the evidence it rests on and naming the signal it came from. Findings
SHALL NOT carry a hypothesis, a root cause, a confidence level, or a
recommended action. An investigation that gathered evidence and found nothing
notable SHALL return findings that say so, which is a success and SHALL NOT be
reported as a failure.

A finding SHALL describe a pattern and illustrate it with a bounded number of
representative examples, together with how many times the pattern was seen.
It SHALL NOT carry every record behind the pattern, so that a report stays
readable however much the service logged.

#### Scenario: Findings carry their evidence
- **WHEN** an investigation observes something about an incident
- **THEN** the observation is returned together with the evidence supporting
  it and the signal it was drawn from

#### Scenario: A pattern seen many times
- **WHEN** an investigation finds a pattern occurring hundreds of times
- **THEN** the finding reports how many times it occurred and carries only a
  bounded number of examples, not one entry per occurrence

#### Scenario: Nothing notable was found
- **WHEN** an investigation queries the platform successfully and finds
  nothing worth reporting
- **THEN** it returns findings stating that nothing notable was found, and the
  investigation counts as successful

#### Scenario: Findings do not conclude
- **WHEN** findings are produced for any incident
- **THEN** they contain no hypothesis, no root cause, and no confidence level

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
normalisation — an identifier, the instant it concerns, a human-readable
summary, and an address at which a human can open the thing itself on the
platform, alongside what the platform actually returned — rather than through
a translation written per tool, so that a specialist reaching a new tool needs
no new rendering.

An item's address SHALL be derived from what was retrieved, never produced by
the reasoning that formed the finding. The system SHALL NOT accept an address
as part of what a specialist reports, because an invented address cannot be
checked against what was retrieved the way an invented identifier can, and a
reader will follow it. An address SHALL be absent where the platform offers no
way to address that item, which is a complete answer rather than a failure:
evidence without an address is still evidence, and the system SHALL render it
as such.

An address SHALL be available at both grains at which evidence is identified.
An individual item SHALL be addressed as that item where the retrieved result
identifies it, and a retrieval SHALL be addressed as the query that produced
it over the window it ran over, so that evidence with no discrete items is
still something a reader can go and look at.

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

#### Scenario: Evidence carries where to go and see it
- **WHEN** a retrieved item is presented to a human and the platform can
  address it
- **THEN** the item carries an address that opens that item on the platform,
  distinct from the summary of what it says

#### Scenario: An item the platform cannot address
- **WHEN** a retrieved item is presented to a human and the platform offers no
  way to address it
- **THEN** the item carries no address, and is still reported with its
  identifier, instant, and summary

#### Scenario: An address is never taken from what a specialist reports
- **WHEN** a specialist's report includes something shaped like an address for
  its evidence
- **THEN** it is not used, and the address a reader is given is the one derived
  from what was retrieved

#### Scenario: An aggregate is addressable
- **WHEN** a finding cites a retrieval that produced no discrete items
- **THEN** the address a reader is given opens the query that produced it over
  the window it ran over

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

### Requirement: A failed investigation is retried on later runs, within a bounded number of attempts
When an incident's investigation fails, the system SHALL investigate it again
on the next run, and SHALL keep doing so until either an investigation produces
findings or the incident has spent its configured number of attempts. The
number of attempts SHALL be an operator-configurable behavior setting with a
documented default of three, counted as the total number of investigations of
that incident — the first one included — so that setting it to one disables
retrying.

Attempts SHALL bound every investigation of an incident, not only the ones
after the first. While an incident has spent its attempts, the system SHALL NOT
investigate it again, however overdue its report is, so that a platform that
stays unreachable costs a bounded number of investigations rather than one per
run for as long as the alerts keep firing.

Attempts SHALL be counted per incident and SHALL survive between runs. An
attempt SHALL be counted only when an investigation fails. The count SHALL be
cleared when a report about the incident is delivered, whatever that report
carried, so that an incident whose alerts return after its cooldown is
investigated afresh rather than staying permanently spent — and so that a
report that failed to deliver leaves the attempt state as it was.

This bound is unrelated to the retries a single platform call makes internally:
one bounds how many times the system tries to investigate an incident at all,
across runs, and the other bounds one call within one investigation.

#### Scenario: A retry on the next run
- **WHEN** an incident's investigation failed and a later run handles it again
- **THEN** the system investigates it again

#### Scenario: Attempts are spent
- **WHEN** an incident's third investigation fails
- **THEN** the system does not investigate that incident again until a report
  about it has been delivered

#### Scenario: An overdue incident with no attempts left is not investigated
- **WHEN** an incident that has spent its attempts is handled by run after run
  while its report is still owed
- **THEN** the system investigates it no further, so the cost of an unreachable
  platform stays bounded

#### Scenario: A successful investigation ends the retrying
- **WHEN** an investigation produces findings and the report carrying them is
  delivered
- **THEN** the incident has no attempts outstanding

#### Scenario: A delivery failure does not spend an attempt
- **WHEN** an investigation produces findings and the report carrying them is
  not delivered
- **THEN** the attempt state is unchanged, and no attempt was spent on the
  successful investigation

#### Scenario: A fresh cycle after a delivered report
- **WHEN** an incident that had spent attempts has a report delivered, and its
  alerts continue past the cooldown
- **THEN** it is investigated again with its full allowance of attempts

#### Scenario: Retrying is disabled
- **WHEN** the operator configures a single attempt
- **THEN** an investigation that fails is not retried

#### Scenario: Attempts survive the process
- **WHEN** an incident's investigation fails, the process ends, and a later
  run continues that incident from a fresh process
- **THEN** the attempt already spent is remembered, so the incident gets the
  remaining attempts and no more

### Requirement: An incident whose investigation never succeeds is reported without findings
When an incident has spent every attempt without an investigation producing
findings, and a report about it is due, the system SHALL deliver a report
carrying the incident's alerts and stating that investigation was attempted and
could not complete. Alerts that fired SHALL NOT go unreported merely because
the system could not investigate them: the delay is the price of trying, and
silence is not.

This report SHALL be the last resort rather than the first response — it SHALL
NOT be delivered while an attempt remains, since a later attempt may still be
able to say something worth reading.

#### Scenario: Every attempt failed
- **WHEN** an incident's third and final investigation fails and its report is
  due
- **THEN** the system delivers a report listing the alerts and saying
  investigation could not complete

#### Scenario: Alerts are not lost to an unreachable platform
- **WHEN** the observability platform is unreachable for the whole life of an
  incident
- **THEN** the team is still told which alerts fired, later than it would have
  been told had the investigation worked

#### Scenario: Not delivered while an attempt remains
- **WHEN** an incident's first investigation fails and two attempts remain
- **THEN** no report is delivered for it yet

### Requirement: Investigation credentials and endpoints come from the environment
The observability platform's location and credentials SHALL be read from the
environment, using the platform's own conventional variable names, and SHALL
NOT be configurable in `config.yaml`. The model an investigation runs on
SHALL be a behavior setting resolved like every other, while the credential
that model needs SHALL be an environment-only deployment fact. That credential,
and which model platform it authenticates against, SHALL be resolved from the
run's environment and supplied to the model, rather than left for the model's
own client to discover. The system SHALL refuse to start when a credential an
investigation needs is absent, rather than failing part-way through a run.

#### Scenario: A credential is missing
- **WHEN** the environment does not supply a credential an investigation
  requires
- **THEN** the system refuses to start and names what is missing, without
  fetching any alerts

#### Scenario: A credential written into the config file
- **WHEN** `config.yaml` contains a key shaped like a platform credential
- **THEN** it is not used to reach the platform, and resolution proceeds as if
  it were absent

#### Scenario: The same behavior against another account
- **WHEN** the same `config.yaml` is deployed against a different platform
  account
- **THEN** only environment values change

#### Scenario: A credential the process never exported
- **WHEN** the model's credential reaches the run's environment without being
  exported by the process
- **THEN** investigations authenticate with it, rather than the model behaving
  as though no credential were configured

#### Scenario: A start that would not have authenticated
- **WHEN** the system starts rather than refusing
- **THEN** the credential it accepted is the one an investigation's model will
  actually use, so a run never passes its startup check and then fails to
  authenticate on its first incident

### Requirement: The model platform an investigation authenticates against
A deployment SHALL choose, through the environment, whether an investigation's
model is reached with an API key or against an enterprise model platform using
the credentials that deployment already holds. The choice SHALL be made from
the run's resolved environment, under the model SDK's own conventional
variable names, and SHALL determine how the model is reached. A deployment
that names an enterprise project and location SHALL have them used; one that
names neither SHALL fall back to whatever that platform's own credential
discovery provides.

#### Scenario: An API key deployment
- **WHEN** the environment supplies an API key and does not select an
  enterprise platform
- **THEN** investigations reason through the key, and no enterprise project or
  location is required

#### Scenario: An enterprise deployment
- **WHEN** the environment selects the enterprise platform
- **THEN** investigations reason against that platform, and the run does not
  refuse for having no API key

#### Scenario: An enterprise deployment naming its project
- **WHEN** the environment selects the enterprise platform and names a project
  and location
- **THEN** investigations are made against that project and location

#### Scenario: Neither is configured
- **WHEN** the environment supplies no API key and selects no enterprise
  platform
- **THEN** the run refuses to start and names both ways of configuring it
