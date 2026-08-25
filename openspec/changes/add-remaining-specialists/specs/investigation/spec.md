## ADDED Requirements

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
  window
- **THEN** the findings say so rather than describing a request that was never
  seen

### Requirement: The infrastructure specialist reports the resources underneath the service
The infrastructure specialist SHALL examine what the incident's service runs on
over the incident's window and report the resource pressure it finds — CPU,
memory, disk and network — naming what was saturated, how far, and when relative
to the alerts. It SHALL cite the evidence behind each observation.

Where the platform can identify the workload the service runs as, the
specialist SHALL report its state over the window, including restarts and
scheduling failures. Where the platform cannot, that SHALL be an ordinary empty
result rather than an error.

#### Scenario: A host is under memory pressure
- **WHEN** the hosts serving the service approached their memory limit during
  the window
- **THEN** the findings name the pressure, how far it went, and when it began

#### Scenario: A workload was restarting
- **WHEN** the workload the service runs as restarted repeatedly during the
  window
- **THEN** the findings report the restarts, citing what they were read from

#### Scenario: The infrastructure was healthy
- **WHEN** the resources underneath the service were unremarkable through the
  window
- **THEN** the findings say so rather than reporting pressure that was not
  there

### Requirement: A signal a deployment does not have is an empty result, not a failed retrieval
When a specialist asks the platform for a signal a deployment genuinely does
not have — no container workload, no instrumented traces, no host metrics for a
managed service — the platform's empty answer SHALL be recorded as a retrieval
that succeeded and returned nothing. It SHALL NOT be recorded as a failed
retrieval, and the investigation SHALL NOT be marked incomplete on the strength
of it.

Only a retrieval the platform refused, could not serve, or answered with
something unreadable SHALL count as a failure. "The platform has nothing to say
here" and "the platform could not answer" are different facts, and the system
SHALL NOT allow the first to be recorded as the second.

This is the failed-retrieval requirement pointed the other way, and both
protect the same reader: one stops a broken search reading as a quiet service,
and this stops a quiet service reading as a broken search.

#### Scenario: A service that does not run on containers
- **WHEN** a specialist searches for the container workload of a service that
  has none, and the platform answers that there are none
- **THEN** the retrieval is recorded as successful with nothing in it, and the
  investigation is not marked incomplete

#### Scenario: An empty answer and a refused one are distinguishable
- **WHEN** one retrieval comes back empty and another is refused by the
  platform
- **THEN** only the second is recorded as a failure

#### Scenario: A deployment with no trace instrumentation
- **WHEN** every retrieval a specialist attempts comes back empty because the
  deployment does not carry that signal
- **THEN** the investigation completes, reports no findings from that
  specialist, and is not reported as a failure

#### Scenario: An unreadable answer is still a failure
- **WHEN** a retrieval comes back carrying nothing that can be read at all
- **THEN** it is recorded as a failed retrieval, because the system cannot tell
  an empty answer from a broken one
