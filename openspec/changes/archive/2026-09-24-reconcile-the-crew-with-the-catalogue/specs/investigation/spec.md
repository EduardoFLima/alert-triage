## MODIFIED Requirements

### Requirement: The APM specialist reports the service's golden signals and what changed around them
The APM specialist SHALL examine the incident's service over the incident's
window and report what its latency, error rate and throughput did — what moved,
by how much, and when it moved relative to the alerts. It SHALL cite the
evidence behind each observation, and SHALL NOT report a movement it did not
observe in retrieved evidence.

It SHALL also report single-hop dependency evidence: what the service's
immediate upstream and downstream neighbours were doing over the same window,
where the platform can say. It SHALL NOT investigate those neighbours in their
own right — a neighbour is context for this service's behaviour, not a second
investigation.

Which services are a neighbour SHALL itself be retrieved rather than assumed.
A neighbour the specialist named without the platform having said so is a
fabrication of the same kind as an invented log line, and SHALL be treated as
one: the naming of a neighbour is an observation, and it cites what it was
read from.

It SHALL report whether a change to the service landed close enough to the
alerts to be worth a reader's attention, and SHALL treat the coincidence as
something observed rather than as a cause. Naming a change as the cause is a
conclusion, which no specialist is entitled to state.

#### Scenario: Latency degraded during the window
- **WHEN** the service's latency rose sharply while its alerts were firing
- **THEN** the findings name that movement, its size, and when it began
  relative to the alerts

#### Scenario: A neighbouring service is implicated
- **WHEN** the service's degradation coincides with a change in traffic from
  an immediate neighbour
- **THEN** the findings report what the neighbour was doing as evidence about
  this service, and no investigation of the neighbour is performed

#### Scenario: A neighbour nobody retrieved
- **WHEN** a finding names an upstream or downstream service that no retrieval
  identified as a neighbour of the incident's service
- **THEN** the finding is treated as evidence that cannot be traced back to
  what was retrieved, and is discarded

#### Scenario: A change landed just before the alerts
- **WHEN** a deployment or configuration change to the service is recorded
  shortly before the alerts began
- **THEN** the findings report the change and when it landed, without naming
  it as the cause

#### Scenario: The golden signals are unremarkable
- **WHEN** the service's latency, error rate and throughput held steady
  through the window
- **THEN** the findings say so rather than manufacturing a movement

### Requirement: The trace specialist reports what a slow or failed request spent its time on
The trace specialist SHALL find requests to the incident's service that were
slow or that failed during the incident's window, and SHALL report where their
time went or where they broke — which operation dominated, and what it was
waiting on. It SHALL cite the trace evidence behind each observation.

It SHALL report about requests it actually retrieved. A description of how such
a request would typically behave is not a finding, and SHALL NOT be presented as
one.

A retrieval that returned nothing SHALL NOT be reported as a service that had
nothing slow or failing, where what was asked for cannot be shown to exist. A
query naming an attribute the service does not carry returns empty for a reason
that is about the query, and the two readings are opposite findings. The
specialist SHALL establish that what it queried on is something the service
reports before it reports an empty answer as an account of the service — the
same discipline the specialists querying metrics are held to.

#### Scenario: A slow request is examined
- **WHEN** the service served requests far slower than usual during the window
- **THEN** the findings name what those requests spent their time on, citing
  the traces they were read from

#### Scenario: A failing request is examined
- **WHEN** requests to the service failed during the window
- **THEN** the findings name where they broke, citing the traces they were read
  from

#### Scenario: Nothing slow or failing was retrieved
- **WHEN** no slow or failed request for the service can be retrieved for the
  window, and what was queried on is something the service is known to report
- **THEN** the findings say so rather than describing a request that was never
  seen

#### Scenario: The query named something the service does not carry
- **WHEN** a span query returns nothing and the attribute it filtered on has
  not been shown to be one the service reports
- **THEN** that is not reported as a service with nothing slow or failing

### Requirement: The infrastructure specialist reports the resources underneath the service
The infrastructure specialist SHALL examine what the incident's service runs on
over the incident's window and report the resource pressure it finds — CPU,
memory, disk and network — naming what was saturated, how far, and when relative
to the alerts. It SHALL cite the evidence behind each observation.

Where the platform can identify the workload the service runs as, the
specialist SHALL report its state over the window, including restarts and
scheduling failures. Where the platform cannot, that SHALL be an ordinary empty
result rather than an error.

Where the platform can account for how that workload was most recently rolled
out, the specialist SHALL report that account alongside the workload's state,
so that a workload which changed during or shortly before the window is
reported as having changed. That account SHALL be an observation like any
other: it is reported with when it happened, and SHALL NOT be named as the
cause of the alerts.

#### Scenario: A host is under memory pressure
- **WHEN** the hosts serving the service approached their memory limit during
  the window
- **THEN** the findings name the pressure, how far it went, and when it began

#### Scenario: A workload was restarting
- **WHEN** the workload the service runs as restarted repeatedly during the
  window
- **THEN** the findings report the restarts, citing what they were read from

#### Scenario: A rollout landed near the alerts
- **WHEN** the workload the service runs as was rolled out shortly before or
  during the window
- **THEN** the findings report the rollout and when it happened, without naming
  it as the cause

#### Scenario: A rollout is analysed for a workload that was retrieved
- **WHEN** the specialist reports on a workload's rollout
- **THEN** the workload it reports on is one an earlier retrieval identified,
  rather than one the specialist named unaided

#### Scenario: The infrastructure was healthy
- **WHEN** the resources underneath the service were unremarkable through the
  window
- **THEN** the findings say so rather than reporting pressure that was not
  there
