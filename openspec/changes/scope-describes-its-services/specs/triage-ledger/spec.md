## MODIFIED Requirements

### Requirement: An incident closes once it can no longer affect a decision
The system SHALL treat an incident as closed once it can neither be continued
nor suppress a report — that is, once its latest alert has passed the
continuation window and no report is due for it. A closed incident SHALL take
no part in any subsequent decision: it SHALL NOT be continued by later alerts,
and it SHALL NOT suppress a later report. Closing is a change of standing, not
a deletion — the record remains available for a human to consult.

"No report is due" is the same question a run asks before delivering anything,
asked once more at closing time rather than answered a second way. It holds for
an incident reported longer ago than the cooldown, and it holds for an incident
the run deliberately left alone as within its service's acceptable latency —
which is what stops such an incident, never reported and never to be, from
staying open forever and growing the ledger without bound.

It does not hold for an incident that still owes a report: one whose
investigations have failed while attempts remain has never been reported and
is due, so it stays open however quiet its service has gone. Closing it would
discard the attempts it had spent and let the next run open a fresh incident
for the same problem, which is the unbounded investigating the attempt bound
exists to prevent.

#### Scenario: A long-quiet incident closes
- **WHEN** an incident's latest alert is older than the grouping window and it
  was last reported longer ago than the cooldown
- **THEN** the system treats it as closed

#### Scenario: A quiet but recently reported incident stays open
- **WHEN** an incident's latest alert is older than the grouping window but the
  cooldown since its last report has not elapsed
- **THEN** the system keeps it open, so that a re-fire within the cooldown is
  still suppressed

#### Scenario: An incident nobody was owed a report about closes
- **WHEN** an incident was left alone as within its service's acceptable
  latency, was never reported, and its latest alert is older than the grouping
  window
- **THEN** the system treats it as closed, because no report is due for it and
  none ever was

#### Scenario: An incident that still owes a report stays open
- **WHEN** an incident has never been reported because every investigation of
  it has failed while attempts remain, and its latest alert is older than the
  grouping window
- **THEN** the system keeps it open, because a report is still due for it

#### Scenario: A closed incident is not continued
- **WHEN** alerts for a service arrive after that service's only incident has
  closed, and they would have continued it had it still been open
- **THEN** the system opens a new incident with a new identifier, and the
  closed incident is left as it stands

#### Scenario: A closed incident does not suppress a report
- **WHEN** a new incident opens on a service whose closed incident was reported
  more recently than the cooldown would allow
- **THEN** the system reports the new incident, because a closed incident's
  last report no longer suppresses anything
