## ADDED Requirements

### Requirement: A run investigates an incident when a report is due or a retry is owed
A run SHALL investigate an incident when its report is due, and also when the
incident has an investigation retry owed, even though no report is due for it.
It SHALL investigate after deciding, and before building any report, and SHALL
build a report it delivers from the findings the investigation returned. It
SHALL NOT investigate an incident that is neither due nor owed a retry, and
SHALL NOT investigate an incident it could not read from the ledger.

#### Scenario: A due incident is investigated
- **WHEN** a run decides a report is due for an incident
- **THEN** it investigates that incident and delivers a report built from the
  findings

#### Scenario: A suppressed report costs no investigation
- **WHEN** a run continues an incident inside its cooldown with no retry owed
- **THEN** it investigates nothing for that incident and delivers nothing

#### Scenario: A retry is investigated without a report being due
- **WHEN** a run continues an incident that is inside its cooldown and has a
  retry owed
- **THEN** it investigates that incident

#### Scenario: Each group is investigated on its own
- **WHEN** a run has three due incidents across three services
- **THEN** each is investigated for its own service and window, and the
  findings of one never appear in another's report

### Requirement: A due report is delivered whether or not its investigation succeeded
When the investigation of an incident whose report is due fails, a run SHALL
deliver a report about that incident anyway, stating that investigation was
attempted and did not complete. It SHALL continue with the remaining groups,
record the incident as it records any other, and finish unsuccessfully, naming
the stage and the service. It SHALL NOT retry the investigation within the same
run — a retry belongs to the next run.

#### Scenario: Investigation fails for one service
- **WHEN** a run handles three due incidents and the investigation fails for
  the second
- **THEN** all three are reported and recorded, the second's report says the
  investigation did not complete, and the run finishes unsuccessfully

#### Scenario: The cooldown still runs from the delivered report
- **WHEN** a report whose investigation failed is delivered and accepted
- **THEN** the incident is recorded as reported at the run's instant, exactly
  as any delivered report is

#### Scenario: One failure, one attempt
- **WHEN** an investigation fails during a run
- **THEN** the run does not investigate that incident again before it finishes

#### Scenario: The failure is diagnosable
- **WHEN** an investigation fails
- **THEN** the run's output names investigation as the stage that failed and
  the service it concerned

### Requirement: A retry is reported only when it changes what the team knows
When a run investigates an incident because a retry is owed rather than
because a report is due, it SHALL deliver a report only if that investigation
produced findings. A retry that fails again SHALL deliver nothing, because it
tells the team nothing it was not already told. A retry that produces findings
SHALL deliver them even though the re-notify cooldown has not elapsed, and the
report SHALL make clear that it follows an earlier report that carried no
findings, so a second message inside the cooldown is legible rather than
mysterious.

A run SHALL record the incident in either case, and SHALL finish unsuccessfully
when a retry's investigation failed, exactly as it does for a due report's
investigation.

#### Scenario: A retry fails again
- **WHEN** a second investigation of an incident fails
- **THEN** the run delivers nothing for that incident, records it with the
  attempt spent, and finishes unsuccessfully

#### Scenario: A retry succeeds
- **WHEN** a third investigation of an incident produces findings
- **THEN** the run delivers a report carrying them, even though the cooldown
  has not elapsed, and records the incident as reported at the run's instant

#### Scenario: The follow-up report explains itself
- **WHEN** a report is delivered because a retry finally produced findings
- **THEN** its body makes clear that it follows an earlier report about the
  same incident that could not carry any

#### Scenario: A retry that found nothing notable still counts as a change
- **WHEN** a retry completes successfully and finds nothing notable
- **THEN** the run delivers a report saying so, because an investigation that
  ran and found nothing is not what the earlier report said

#### Scenario: Attempts are spent and the incident is left alone
- **WHEN** an incident has spent its configured attempts without ever
  producing findings
- **THEN** later runs neither investigate nor report it until its cooldown
  elapses, and it is still recorded and still absorbs new alerts

## MODIFIED Requirements

### Requirement: The report a run sends
A run SHALL build each report from the incident and the findings of its
investigation. The report SHALL name the incident's service in its subject,
and its body SHALL carry both what the investigation found, with the evidence
behind it, and the alerts absorbed into the incident — when they fired, their
titles, and the links back to the platform that reported them.

When no findings are available because the investigation did not complete, the
report SHALL carry the alerts as above and SHALL state plainly that
investigation was attempted and did not complete, rather than presenting
itself as triage. A report SHALL NOT present a hypothesis, a root cause, or a
confidence level, none of which an investigation produces yet.

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
- **WHEN** a report is built for an incident whose investigation did not
  complete
- **THEN** its body says investigation was attempted and did not complete,
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
