## Purpose

What the system does with an incident before it reports it: the evidence it
gathers around the alert window, what it is allowed to say about that
evidence, and what happens when the gathering cannot complete. Investigation
is the first-pass legwork a knowledgeable human would do, kept separate from
the conclusion drawn from it.

## ADDED Requirements

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

#### Scenario: Findings carry their evidence
- **WHEN** an investigation observes something about an incident
- **THEN** the observation is returned together with the evidence supporting
  it and the signal it was drawn from

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

#### Scenario: One specialist today
- **WHEN** the system investigates an incident with only the logs specialist
  available
- **THEN** it returns findings from that specialist alone, in the same form a
  multi-specialist investigation returns

#### Scenario: A specialist is added
- **WHEN** a further specialist is introduced
- **THEN** the caller requesting an investigation is unchanged

### Requirement: The logs specialist reports error and warning patterns
The logs specialist SHALL examine the incident's service over the incident's
window and report the error and warning patterns it finds — what recurs, at
what rate, and when it started relative to the alerts. It SHALL cite the log
evidence behind each observation, and SHALL NOT report a pattern it did not
observe in retrieved logs.

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

### Requirement: Evidence is gathered through a platform boundary
Specialist agents SHALL obtain observability evidence — logs, and later
traces and metrics — through a single boundary expressed in this project's
vocabulary, and SHALL NOT depend on any one observability platform's API,
wire format, or tool names. Substituting a different observability platform
SHALL require no change to any specialist agent.

#### Scenario: A different platform is substituted
- **WHEN** the observability platform behind the boundary is replaced
- **THEN** the specialist agents are unchanged

#### Scenario: An investigation without a platform
- **WHEN** an investigation is exercised against a substitute for the
  observability platform
- **THEN** it completes with no real platform, network, or credentials
  involved

### Requirement: An investigation that cannot complete degrades, it does not block
When an investigation cannot complete — the observability platform is
unreachable or refuses the request, the model fails, or the investigation
errors for any other reason — the system SHALL return no findings rather than
partial ones presented as complete, and SHALL report that the investigation
did not complete along with why. The caller SHALL still be able to deliver a
report. A failed investigation SHALL NOT suppress a due report, and SHALL NOT
prevent the incident from being recorded.

#### Scenario: The observability platform is unreachable
- **WHEN** an investigation cannot reach the platform
- **THEN** it reports that it did not complete, naming the reason, and returns
  no findings

#### Scenario: A due report still goes out
- **WHEN** an investigation for a due incident fails
- **THEN** the caller is still able to deliver a report about that incident

#### Scenario: Failure is distinguishable from a quiet result
- **WHEN** an investigation fails
- **THEN** the outcome is distinguishable from an investigation that
  succeeded and found nothing notable

### Requirement: Investigation credentials and endpoints come from the environment
The observability platform's location and credentials SHALL be read from the
environment, using the platform's own conventional variable names, and SHALL
NOT be configurable in `config.yaml`. The model an investigation runs on
SHALL be a behavior setting resolved like every other, while the credential
that model needs SHALL be an environment-only deployment fact. The system
SHALL refuse to start when a credential an investigation needs is absent,
rather than failing part-way through a run.

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
