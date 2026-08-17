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

### Requirement: Evidence in a finding is always evidence the platform returned
The evidence carried by a finding SHALL consist only of records the
observability platform actually returned during that investigation. The system
SHALL NOT present as evidence any text produced by the reasoning that formed
the finding, however plausible it looks. Evidence SHALL be identified against
what was retrieved and reproduced from the retrieved record, so that a
fabricated or mistaken reference cannot be rendered into a report.

A finding whose evidence cannot be traced back to retrieved records SHALL be
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

#### Scenario: Evidence names a record that was never retrieved
- **WHEN** a finding's evidence refers to a log record the platform did not
  return during the investigation
- **THEN** the finding is discarded, the discard is recorded, and it does not
  appear in any report

#### Scenario: One bad finding among good ones
- **WHEN** an investigation produces three findings and only one has evidence
  that cannot be traced to retrieved records
- **THEN** the other two are returned and reported, and the investigation is
  not treated as a failure

#### Scenario: Nothing survives the check
- **WHEN** every finding an investigation produced has untraceable evidence
- **THEN** the investigation returns no findings, which is reported as nothing
  notable rather than as a failed investigation

#### Scenario: Evidence is reproduced, not restated
- **WHEN** a finding's evidence is presented to a human
- **THEN** what they read is the retrieved record itself, not a retelling of it

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

### Requirement: A failed investigation is retried on later runs, within a bounded number of attempts
When an incident has been reported without findings because its investigation
did not complete, the system SHALL investigate it again on the next run, and
SHALL keep doing so until either an investigation produces findings that reach
the team or the incident has spent its configured number of attempts. The
number of attempts SHALL be an operator-configurable behavior setting with a
documented default of three, counted as the total number of investigations of
that incident — the first one included — so that setting it to one disables
retrying.

Attempts SHALL be counted per incident and SHALL survive between runs.
An attempt SHALL be counted only when an investigation fails; an investigation
that succeeds SHALL clear the count once its findings have been delivered, so
that a delivery failure leaves the retry owed rather than spending it. Once the
attempts are spent, the system SHALL stop retrying and SHALL leave the incident
governed by the re-notify cooldown alone.

This bound is unrelated to the retries a single platform call makes internally:
one bounds how many times the system tries to investigate an incident at all,
across runs, and the other bounds one call within one investigation.

#### Scenario: A retry on the next run
- **WHEN** an incident was reported without findings and a later run continues
  it
- **THEN** the system investigates it again, even though no report is due

#### Scenario: Attempts are spent
- **WHEN** an incident's third investigation fails
- **THEN** the system does not investigate it again for that cycle, and the
  incident is governed by the cooldown alone

#### Scenario: A successful retry ends the retrying
- **WHEN** a retry produces findings and they are delivered
- **THEN** the incident has no attempts outstanding, and a later run does not
  retry it

#### Scenario: A delivery failure does not spend an attempt
- **WHEN** a retry produces findings and the report carrying them is not
  delivered
- **THEN** the retry is still owed at the next run, and no attempt was spent
  on the successful investigation

#### Scenario: Retrying is disabled
- **WHEN** the operator configures a single attempt
- **THEN** an investigation that fails is not retried, and the incident is
  governed by the cooldown alone

#### Scenario: Attempts survive the process
- **WHEN** an incident's investigation fails, the process ends, and a later
  run continues that incident from a fresh process
- **THEN** the attempt already spent is remembered, so the incident gets the
  remaining attempts and no more

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
