## ADDED Requirements

### Requirement: An incident within its service's acceptable latency is left alone
Where a watched service declares an acceptable latency, a run SHALL leave an
incident on that service alone when every alert absorbed into it reports a
latency at or under that figure. Leaving it alone means no investigation and no
report: nothing about it is worth a model's time or a team's attention, and
telling a team about a service performing as they said it should is the alert
fatigue this system exists to reduce, reintroduced one layer up.

A run SHALL still record such an incident, with its new alerts absorbed, so
that an overlapping run recognises it rather than opening a second incident for
the same alerts. It SHALL NOT stamp it as reported, because nothing was
delivered, and SHALL NOT spend an investigation attempt on it, because none was
attempted. A run that left incidents alone and did everything else it set out
to do SHALL finish successfully: a deliberate silence is not a failure.

Silence SHALL only ever be chosen against figures that were actually read. An
incident SHALL be investigated as usual when any alert in it reports no
latency, when any alert in it reports a latency above the figure, or when its
service declares no acceptable latency at all. It follows that absorbing an
alert can end an incident's silence and can never begin it, so an incident
already investigated is not silenced by the quieter alerts that join it later.

A run's account SHALL say which incidents it left alone and that the acceptable
latency is why, so that a reader can tell an incident nobody looked at from one
the run never saw.

#### Scenario: Every alert is within the acceptable latency
- **WHEN** a run handles an incident on a service declaring an acceptable
  latency, and every alert in it reports a latency at or under that figure
- **THEN** the run investigates nothing and delivers nothing for that incident,
  records it with its alerts absorbed, and finishes successfully

#### Scenario: One alert is above the figure
- **WHEN** an incident holds three alerts, two within the acceptable latency
  and one above it
- **THEN** the run investigates and reports the incident as it would any other

#### Scenario: An alert nobody measured
- **WHEN** an incident holds one alert within the acceptable latency and one
  reporting no latency at all
- **THEN** the run investigates and reports the incident, because an
  unmeasured alert has not been shown to be acceptable

#### Scenario: The service declares no acceptable latency
- **WHEN** an incident's service declares no acceptable latency and its alerts
  report low latencies
- **THEN** the run investigates and reports the incident, because no figure was
  ever stated to judge it against

#### Scenario: A quiet alert does not silence a loud incident
- **WHEN** an incident that was investigated for an alert above the acceptable
  latency absorbs a further alert below it
- **THEN** the incident is still investigated and reported, because the alert
  that warranted it is still absorbed in it

#### Scenario: The cooldown is untouched
- **WHEN** a run leaves an incident alone for being within its acceptable
  latency
- **THEN** the incident's last-reported instant and its investigation attempts
  are left exactly as they were

#### Scenario: A deliberate silence is diagnosable
- **WHEN** a run leaves an incident alone for being within its acceptable
  latency
- **THEN** the run's output names that incident and says the acceptable latency
  is why nothing was done about it

### Requirement: A report about a critical service says so
Where a watched service is declared critical, a run SHALL make that plain in
the report it delivers about an incident on that service, in the one line that
announces the report, so that a reader scanning a list of subjects can tell
which one to open first.

Criticality SHALL change how a report reads and nothing else. It SHALL NOT
change when a report is delivered, which channels carry it, whether the
incident is investigated, or how long its cooldown runs — a service being
important is not a reason to tell a team about it more often than they asked.

A report about a service that is not critical SHALL read exactly as it does
today, so that the marking means something by its absence as well as by its
presence.

#### Scenario: A critical service's report is marked
- **WHEN** a report is delivered for an incident on a service declared critical
- **THEN** its subject says the service is critical, alongside what the subject
  already carried

#### Scenario: An ordinary service's report is unchanged
- **WHEN** a report is delivered for an incident on a service that is not
  declared critical
- **THEN** its subject carries no criticality marking

#### Scenario: Criticality changes no cadence
- **WHEN** two incidents are handled in one run, one on a critical service and
  one not, both inside their cooldowns
- **THEN** neither is reported, because criticality does not override the
  cooldown

#### Scenario: Criticality does not force an investigation
- **WHEN** an incident on a critical service is within that service's
  acceptable latency
- **THEN** the run still leaves it alone, because a service being important
  does not make a measurement that was fine into a problem
