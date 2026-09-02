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

### Requirement: A report says which signals were examined
A report SHALL make plain which observability signals the investigation behind
it actually consulted, so that a reader can tell what was covered from what was
not. A report SHALL NOT name one signal when several were consulted, nor imply
coverage of a signal no specialist looked at.

What a report claims SHALL be what the investigation did, not what the
deployment could have done. A signal a specialist exists for but was not
consulted about SHALL NOT be named as examined, because an investigation that
chose not to look at a signal and one that looked and found it clean are
opposite pieces of news.

This matters most where nothing was found. "Nothing notable" is only
interpretable against a scope: a reader told the logs were clean draws a
different conclusion from one told the logs, the golden signals, the traces and
the infrastructure were all clean, and the report SHALL NOT leave them guessing
which they were told.

An investigation that consulted no signal at all SHALL be reported as such, and
SHALL NOT be reported as one that found nothing notable.

#### Scenario: Nothing notable across several signals
- **WHEN** an investigation consults several specialists and finds nothing
  notable in any of them
- **THEN** the report says nothing notable was found and names the signals that
  were consulted, rather than naming one of them

#### Scenario: A signal that was not consulted
- **WHEN** an investigation consults two of the four declared specialists and
  finds nothing notable
- **THEN** the report names those two signals as examined and does not present
  the other two as clean

#### Scenario: Findings name the signal they came from
- **WHEN** a report carries findings drawn from more than one signal
- **THEN** each finding is attributed to the signal it was drawn from

#### Scenario: No signal was consulted
- **WHEN** an investigation completes having consulted no specialist
- **THEN** the report says no signal was examined, rather than saying nothing
  notable was found

#### Scenario: The wording survives a specialist being added
- **WHEN** a further specialist joins the crew
- **THEN** the report's account of what was examined still names exactly the
  signals that were consulted, and no report claims a scope wider than what ran
### Requirement: The report a run sends
A run SHALL build each report from the incident and its investigation. The
report SHALL name the incident's service in its subject, and its body SHALL
carry what the investigation concluded, what it found with the evidence behind
it, and the alerts absorbed into the incident — when they fired, their titles,
and the links back to the platform that reported them.

A report of a concluded investigation SHALL state the hypothesis and the
confidence level the investigation attached to it, and SHALL present both as
what they are: a first-pass conclusion offered for a human to act on or
disagree with, never a verdict and never an instruction. The report SHALL NOT
present a hypothesis the investigation did not produce, and SHALL NOT state a
confidence level of its own.

The hypothesis SHALL NOT displace what it was drawn from. A report carrying a
conclusion SHALL still carry the findings and the evidence beneath them, so
that a reader can check the conclusion rather than take it.

Evidence in a report SHALL carry its own link back to the platform, where the
evidence has one, so that a reader who wants to see a finding for themselves
can go from the report to the thing it rests on. A link SHALL be rendered as
an address standing on its own, distinct from the text of what was retrieved,
so that a channel which turns addresses into links finds a whole one and a
channel which does not still shows a reader something they can copy. The
system SHALL NOT render a link inside a passage of text that is subject to
truncation, because a truncated address is worse than none: it still reads as
a link and leads somewhere the evidence is not.

When the investigation behind a report could not gather all the evidence it
asked for, the report SHALL say so, so that a reader can tell findings drawn
from everything the platform holds from findings drawn from part of it. A
report SHALL NOT present a partially evidenced investigation as a complete
one.

When no findings are available because every investigation of the incident
failed, the report SHALL carry the alerts as above and SHALL state plainly
that investigation was attempted and could not complete, rather than
presenting itself as triage. Such a report SHALL carry no hypothesis and no
confidence level, because no investigation produced one.

#### Scenario: A report identifies its service and alerts
- **WHEN** a report is built for an incident with three alerts
- **THEN** its subject names the service and its body lists all three alerts
  with their times and links

#### Scenario: A report carries what was found
- **WHEN** an investigation returned findings for an incident
- **THEN** the report's body states those findings and the evidence behind
  them

#### Scenario: A report carries what was concluded
- **WHEN** an investigation returned a hypothesis and a confidence level
- **THEN** the report's body states both, and states them as a hypothesis
  rather than as a verdict or an instruction

#### Scenario: The report does not pretend to conclude
- **WHEN** a report is built from an investigation that produced a hypothesis
- **THEN** its body presents the hypothesis and its confidence level as a
  first-pass conclusion offered for a human to judge or disagree with, and
  recommends no action and takes none

#### Scenario: The conclusion does not replace the evidence
- **WHEN** a report carries a hypothesis
- **THEN** it also carries the findings and evidence the hypothesis was drawn
  from

#### Scenario: An investigation that concluded nothing
- **WHEN** an investigation completed but produced no hypothesis
- **THEN** the report carries its findings and evidence and states no
  hypothesis, rather than one the report composed

#### Scenario: Evidence in a report can be followed
- **WHEN** a report is built from findings whose evidence carries links
- **THEN** each such piece of evidence appears with its link, and a reader can
  follow it to that evidence on the platform

#### Scenario: Evidence with no link is still reported
- **WHEN** a report is built from findings whose evidence carries no link
- **THEN** that evidence appears with its time and summary as before, and the
  report notes no absence

#### Scenario: A link is never truncated
- **WHEN** a piece of evidence carries a link and a long summary
- **THEN** the summary may be shortened and the link is rendered whole

#### Scenario: The report does not pretend to be triage
- **WHEN** a report is built for an incident whose investigations all failed
- **THEN** its body says investigation was attempted and could not complete,
  and carries no hypothesis and no confidence level

#### Scenario: The report does not pretend to be complete
- **WHEN** a report is built from findings whose investigation could not
  gather part of its evidence
- **THEN** its body says the evidence gathered was incomplete, alongside the
  findings it did produce

#### Scenario: A complete investigation reads as one
- **WHEN** a report is built from findings whose investigation gathered
  everything it asked for
- **THEN** its body carries no incompleteness note, whether or not the
  findings were notable

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
