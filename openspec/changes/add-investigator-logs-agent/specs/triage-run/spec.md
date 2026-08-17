## ADDED Requirements

### Requirement: A run investigates an incident that is due or owed a retry, while attempts remain
A run SHALL investigate an incident when its report is due, and also when the
incident's last investigation failed, even though no report is due for it. In
both cases it SHALL investigate only while the incident has investigation
attempts remaining. It SHALL investigate after deciding, and before building
any report, and SHALL build any report it delivers from the findings the
investigation returned. It SHALL NOT investigate an incident that is neither
due nor owed a retry, an incident that has spent its attempts, or an incident
it could not read from the ledger.

#### Scenario: A due incident is investigated
- **WHEN** a run decides a report is due for an incident with attempts
  remaining
- **THEN** it investigates that incident and delivers a report built from the
  findings

#### Scenario: A quiet incident costs no investigation
- **WHEN** a run continues an incident inside its cooldown whose last
  investigation succeeded
- **THEN** it investigates nothing for that incident and delivers nothing

#### Scenario: A retry is investigated without a report being due
- **WHEN** a run continues an incident inside its cooldown whose last
  investigation failed, with attempts remaining
- **THEN** it investigates that incident

#### Scenario: A spent incident is not investigated however overdue it is
- **WHEN** a run handles an incident that has spent its attempts and whose
  report is still owed
- **THEN** it does not investigate that incident

#### Scenario: Each group is investigated on its own
- **WHEN** a run has three due incidents across three services
- **THEN** each is investigated for its own service and window, and the
  findings of one never appear in another's report

### Requirement: A run delivers a report only when it has something to say
A run SHALL deliver a report about an incident when its investigation produced
findings, and otherwise only when the incident has spent every attempt and a
report is due. An investigation that failed while attempts remain SHALL
produce no report at all, because it tells the team nothing it can act on.

A run SHALL record the incident whether or not it delivered anything, and
SHALL finish unsuccessfully whenever an investigation failed, naming the stage
and the service, so that a silent run and a healthy run are still told apart
from outside the process.

#### Scenario: Findings are delivered
- **WHEN** an investigation produces findings for an incident whose report is
  due
- **THEN** the run delivers a report carrying them and records the incident as
  reported at the run's instant

#### Scenario: A first failure says nothing
- **WHEN** an incident's first investigation fails and attempts remain
- **THEN** the run delivers nothing for it, records it with the attempt spent,
  and finishes unsuccessfully

#### Scenario: A retry fails again
- **WHEN** a second investigation of an incident fails and an attempt remains
- **THEN** the run again delivers nothing, records the incident with the
  attempt spent, and finishes unsuccessfully

#### Scenario: A retry succeeds
- **WHEN** a later investigation of an incident produces findings
- **THEN** the run delivers a report carrying them, and the incident has no
  attempts outstanding

#### Scenario: The last attempt fails
- **WHEN** an incident's final investigation fails and its report is due
- **THEN** the run delivers a report listing the alerts and saying
  investigation could not complete, records the incident as reported, and
  finishes unsuccessfully

#### Scenario: An investigation that found nothing notable is still delivered
- **WHEN** an investigation completes and finds nothing notable
- **THEN** the run delivers a report saying so, because an investigation that
  ran and found nothing is a result

#### Scenario: A silent run is still diagnosable
- **WHEN** a run investigates two incidents, both investigations fail, and
  nothing is delivered
- **THEN** the run finishes unsuccessfully and its output names investigation
  as the stage that failed and the services it concerned

#### Scenario: One failure, one attempt
- **WHEN** an investigation fails during a run
- **THEN** the run does not investigate that incident again before it finishes

#### Scenario: One group's failure does not cost the others their reports
- **WHEN** a run handles three incidents and the investigation fails for the
  second
- **THEN** the first and third are still investigated and reported, and the
  run finishes unsuccessfully

## MODIFIED Requirements

### Requirement: The report a run sends
A run SHALL build each report from the incident and the findings of its
investigation. The report SHALL name the incident's service in its subject,
and its body SHALL carry both what the investigation found, with the evidence
behind it, and the alerts absorbed into the incident — when they fired, their
titles, and the links back to the platform that reported them.

When no findings are available because every investigation of the incident
failed, the report SHALL carry the alerts as above and SHALL state plainly
that investigation was attempted and could not complete, rather than
presenting itself as triage. A report SHALL NOT present a hypothesis, a root
cause, or a confidence level, none of which an investigation produces yet.

#### Scenario: A report identifies its service and alerts
- **WHEN** a report is built for an incident with three alerts
- **THEN** its subject names the service and its body lists all three alerts
  with their times and links

#### Scenario: A report carries what was found
- **WHEN** an investigation returned findings for an incident
- **THEN** the report's body states those findings and the evidence behind
  them

#### Scenario: The report does not pretend to conclude
- **WHEN** a report is built from findings
- **THEN** its body presents observations and evidence, and offers no
  hypothesis, root cause, or confidence level

#### Scenario: The report does not pretend to be triage
- **WHEN** a report is built for an incident whose investigations all failed
- **THEN** its body says investigation was attempted and could not complete,
  rather than presenting itself as a triage conclusion

#### Scenario: Report content is replaceable
- **WHEN** the way a report's body is produced changes
- **THEN** neither the run's ordering nor any notification channel changes
  with it

### Requirement: Adapters are named in one place only
Concrete adapters SHALL be selected and constructed in a single composition
root, and the run itself SHALL receive them through the ports it depends on.
It SHALL be possible to execute a complete run against substitutes for the
alert source, the ledger, the notifier, and the investigator, with no
observability platform, database file, notification channel, model, or
network involved.

#### Scenario: A run under substitutes
- **WHEN** a run is executed with a fake alert source, ledger, notifier, and
  investigator
- **THEN** it completes end to end without any real integration

#### Scenario: Adding a channel does not touch the run
- **WHEN** a deployment configures a different set of notification channels
- **THEN** the run is unchanged, because it is handed one notifier and never
  learns how many channels are behind it

#### Scenario: Changing the investigator does not touch the run
- **WHEN** the investigation behind the port is replaced
- **THEN** the run is unchanged, because it is handed one investigator and
  never learns which agents or platform are behind it

### Requirement: Unusable configuration prevents the run
When configuration cannot be resolved — the mandatory scope is missing, the
platform credentials are absent, no notification channel is configured, or a
credential an investigation needs is absent — the run SHALL refuse to start,
SHALL fetch nothing, and SHALL finish unsuccessfully with a message naming
what is missing.

#### Scenario: Scope is not set
- **WHEN** neither the config file nor the environment supplies the scope
- **THEN** the run refuses to start and names the missing setting, without
  fetching any alerts

#### Scenario: No channel is configured
- **WHEN** the environment configures no notification channel
- **THEN** the run refuses to start rather than fetching alerts it could tell
  nobody about

#### Scenario: An investigation credential is missing
- **WHEN** the environment does not supply a credential the investigation
  requires
- **THEN** the run refuses to start and names what is missing, rather than
  failing part-way through
