## Purpose

The end-to-end run: one pass that takes recent alerts all the way to a
delivered report, in a fixed order, with defined behavior when any stage
fails, and invokable as a single command by a human or a scheduler.

## Requirements

### Requirement: A run takes alerts end to end in one pass
A run SHALL fetch the recent in-scope alerts, group them into same-incident
groups, decide for each group which incident it belongs to and whether that
incident is due to be reported, deliver a report for every incident that is
due, and record every incident it handled. It SHALL then exit rather than
loop or wait, so that a run is a job a human or a scheduler starts.

#### Scenario: Alerts fired and nothing is on record
- **WHEN** a run fetches alerts for a service with no incident on record
- **THEN** it opens an incident for them, delivers a report, and records the
  incident

#### Scenario: No alerts fired
- **WHEN** a run fetches no alerts
- **THEN** it delivers nothing, records nothing, and finishes successfully

#### Scenario: Several services in one run
- **WHEN** a run fetches alerts for more than one service
- **THEN** each service's alerts are decided and reported on their own,
  independently of the others

#### Scenario: A run terminates
- **WHEN** a run has handled every group it fetched
- **THEN** the process finishes rather than waiting for more alerts

### Requirement: A run decides against a single instant
A run SHALL take the current instant once, at its start, and use that same
value for the lookback bound it fetches from, every cooldown and closure
decision it makes, and every timestamp it records. It SHALL NOT read a clock
again part-way through, so that a slow run cannot reach two decisions from two
different "now"s.

#### Scenario: The fetch bound and the decisions agree
- **WHEN** a run fetches alerts and then decides whether to report them
- **THEN** both use the same instant, regardless of how long the fetch took

#### Scenario: A run is reproducible at a supplied instant
- **WHEN** a run is driven at a supplied instant with the same inputs twice
- **THEN** it reaches the same decisions and produces the same records both
  times

### Requirement: A run fetches over the configured lookback
A run SHALL fetch alerts that fired at or after the run's instant minus the
configured ingestion lookback, so that how far back a run looks is an operator
setting and not a property of the pipeline.

#### Scenario: The operator widens the lookback
- **WHEN** the operator configures a longer lookback and a run starts
- **THEN** the run asks for alerts from correspondingly further back

#### Scenario: Alerts seen twice by overlapping runs
- **WHEN** two consecutive runs' lookbacks overlap and an alert falls in both
- **THEN** the second run recognises it as part of the incident already on
  record rather than opening a second incident for it

### Requirement: A report is delivered before its incident is recorded as reported
A run SHALL deliver a due report and only then record the incident as
reported. When delivery fails, the run SHALL still record the incident with
its new alerts absorbed, but SHALL NOT record it as reported — leaving it due
in the next run.

#### Scenario: Delivery succeeds
- **WHEN** a report is due and a channel accepts it
- **THEN** the run records the incident as reported at the run's instant, and
  the cooldown runs from there

#### Scenario: Delivery fails
- **WHEN** a report is due and delivery fails
- **THEN** the run records the incident with its alerts absorbed but with no
  new report stamped, so the next run attempts the report again

#### Scenario: A suppressed report is not a delivery
- **WHEN** an incident is continued inside its cooldown
- **THEN** the run delivers nothing and records the incident with its new
  alerts absorbed and its previous report stamp untouched

### Requirement: A failed fetch ends the run
When alerts cannot be fetched, a run SHALL stop, deliver nothing, record
nothing, and finish unsuccessfully. It SHALL NOT treat a failed fetch as a
quiet period.

#### Scenario: The alert source fails
- **WHEN** fetching alerts fails
- **THEN** the run finishes unsuccessfully, naming the failure, without
  delivering or recording anything

### Requirement: One group's failure does not cost the others their reports
When handling one group fails — the ledger cannot be read or written, or the
report cannot be delivered — a run SHALL continue with the remaining groups
and SHALL finish unsuccessfully afterwards. It SHALL NOT abandon the run at
the first failure, and SHALL NOT report success when any group was left
unhandled.

#### Scenario: One service's delivery fails
- **WHEN** a run handles three groups and delivery fails for the second
- **THEN** the first and third are still reported and recorded, and the run
  finishes unsuccessfully

#### Scenario: One service's ledger read fails
- **WHEN** the ledger cannot be read for one group
- **THEN** the run skips that group, delivering nothing for it, handles the
  remaining groups, and finishes unsuccessfully

#### Scenario: Every group succeeds
- **WHEN** a run handles every group without failure
- **THEN** it finishes successfully

### Requirement: A run's outcome is readable from outside the process
A run SHALL finish with a status that distinguishes a run that did everything
it set out to do from one that did not, and SHALL emit a human-readable
account of what it fetched, reported, and failed to do. Failures SHALL name
the stage and the service they concern.

#### Scenario: A scheduler reads the outcome
- **WHEN** a run finishes unsuccessfully
- **THEN** the process exits with a non-zero status a scheduler can act on

#### Scenario: A successful run
- **WHEN** a run finishes successfully
- **THEN** the process exits with a zero status

#### Scenario: A failure is diagnosable
- **WHEN** a stage fails for one service
- **THEN** the run's output names the stage that failed and the service it was
  handling

### Requirement: The report a run sends before investigation exists
Until investigation is implemented, a run SHALL build each report from the
incident alone. The report SHALL name the incident's service in its subject,
and its body SHALL carry the alerts absorbed into the incident — when they
fired, their titles, and the links back to the platform that reported them —
and SHALL state plainly that no investigation has been performed.

#### Scenario: A report identifies its service and alerts
- **WHEN** a report is built for an incident with three alerts
- **THEN** its subject names the service and its body lists all three alerts
  with their times and links

#### Scenario: The report does not pretend to be triage
- **WHEN** a report is built before investigation exists
- **THEN** its body says that the alerts have not been investigated, rather
  than presenting itself as a triage conclusion

#### Scenario: Report content is replaceable
- **WHEN** the way a report's body is produced changes
- **THEN** neither the run's ordering nor any notification channel changes
  with it

### Requirement: Adapters are named in one place only
Concrete adapters SHALL be selected and constructed in a single composition
root, and the run itself SHALL receive them through the ports it depends on.
It SHALL be possible to execute a complete run against substitutes for the
alert source, the ledger, and the notifier, with no observability platform,
database file, or notification channel involved.

#### Scenario: A run under substitutes
- **WHEN** a run is executed with a fake alert source, ledger, and notifier
- **THEN** it completes end to end without any real integration

#### Scenario: Adding a channel does not touch the run
- **WHEN** a deployment configures a different set of notification channels
- **THEN** the run is unchanged, because it is handed one notifier and never
  learns how many channels are behind it

### Requirement: Unusable configuration prevents the run
When configuration cannot be resolved — the mandatory scope is missing, the
platform credentials are absent, or no notification channel is configured —
the run SHALL refuse to start, SHALL fetch nothing, and SHALL finish
unsuccessfully with a message naming what is missing.

#### Scenario: Scope is not set
- **WHEN** neither the config file nor the environment supplies the scope
- **THEN** the run refuses to start and names the missing setting, without
  fetching any alerts

#### Scenario: No channel is configured
- **WHEN** the environment configures no notification channel
- **THEN** the run refuses to start rather than fetching alerts it could tell
  nobody about

### Requirement: A human can run the job with one command
The job SHALL be invokable as a single command after installation, and the
README SHALL document that command together with what a run needs in its
environment.

#### Scenario: A first manual run
- **WHEN** a developer follows the README's instructions on a machine with the
  project installed
- **THEN** a single documented command performs a complete run

#### Scenario: The command is part of the installed package
- **WHEN** the project is installed
- **THEN** the command is available from the installation, rather than
  requiring a path into the source tree
