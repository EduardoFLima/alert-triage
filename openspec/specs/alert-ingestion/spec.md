## Purpose

Defines how the system obtains the alerts it triages: the AlertSource port
that yields recent in-scope alerts as domain entities, and the guarantees its
adapters must honour around scope filtering, time bounds, completeness, and
failure — so the rest of the pipeline can depend on "these are the alerts,
all of them" without knowing which observability platform produced them.

## Requirements

### Requirement: Alerts fetched in this project's vocabulary
The system SHALL expose alert retrieval behind a port that returns domain
`Alert` entities. The port SHALL NOT expose any observability platform's wire
format, client object, or response type to its callers.

#### Scenario: Caller receives domain entities
- **WHEN** a caller requests recent alerts through the AlertSource port
- **THEN** it receives `Alert` entities carrying the service tag, timestamp,
  source identifier, title, and link, and nothing platform-specific

### Requirement: Only alerts within the configured scope
The system SHALL return only alerts belonging to the owner resolved as
`scope`. Alerts belonging to any other owner SHALL NOT be returned. The
adapter SHALL translate the platform-neutral owner into whatever the platform
uses to express ownership.

#### Scenario: Alerts from another owner are excluded
- **WHEN** the platform holds recent alerts for the configured scope owner and
  for a different owner
- **THEN** only the configured owner's alerts are returned

### Requirement: Only alerts within the requested time bound
The system SHALL return only alerts that fired at or after the instant the
caller asks about, so a recurring run sees recent alerts rather than the
platform's full history.

#### Scenario: Alert fired within the bound
- **WHEN** an in-scope alert fired after the requested instant
- **THEN** it is included in the returned alerts

#### Scenario: Alert fired before the bound
- **WHEN** an in-scope alert fired before the requested instant
- **THEN** it is not included in the returned alerts

### Requirement: Translation of platform alerts into Alert entities
For each alert it retrieves, the system SHALL populate the `Alert` entity's
service tag from the alert's service tag, its timestamp from when the alert
fired, its source identifier from the platform's identifier for that alert,
its title from the alert's title, and its link from the platform's URL for
that alert.

An alert's link SHALL address a page the platform serves, built from an
identifier the platform supports addressing that page by. The system SHALL NOT
build a link by composing an identifier into a route the platform does not
document as accepting it, because such a link is indistinguishable from a
working one until a human follows it and arrives nowhere. Where the alert's
own identifier has no address form, the system SHALL link to the thing that
raised the alert, or to the platform's view of the alert's service over the
period it fired in, in preference to a link known not to open.

An alert's link SHALL carry the reader to what fired at the time it fired,
where the platform's address form allows a period to be expressed, so that a
reader following it days later sees the alert rather than the present.

#### Scenario: Platform alert is translated
- **WHEN** the platform returns an alert carrying a service tag, a fire time,
  an identifier, a title, and a URL
- **THEN** the resulting `Alert` exposes each of those values in the
  corresponding field

#### Scenario: Timestamps are timezone-aware
- **WHEN** an alert is translated from a platform timestamp
- **THEN** its `fired_at` is timezone-aware and expressed in UTC, so grouping
  compares alerts from any source consistently

#### Scenario: A translated alert's link opens
- **WHEN** a human follows the link on a translated alert
- **THEN** the platform serves them a page about that alert, rather than an
  error or an empty view

#### Scenario: The alert's own identifier has no address form
- **WHEN** the platform's identifier for an alert cannot be composed into a
  page address the platform serves
- **THEN** the alert's link addresses what raised it, or the platform's view of
  its service over the period it fired in, and never a route the platform does
  not accept that identifier for

#### Scenario: A link outlives the moment
- **WHEN** a human follows an alert's link some time after it fired
- **THEN** what they are shown covers when the alert fired rather than the
  present moment

### Requirement: Alerts without a resolvable service are excluded
Grouping is keyed on the service tag, so the system SHALL exclude any
retrieved alert from which no service tag can be resolved, rather than
inventing a placeholder service or failing the whole fetch.

#### Scenario: Retrieved alert carries no service tag
- **WHEN** the platform returns a mix of alerts, one of which carries no
  service tag
- **THEN** the remaining alerts are returned and the one without a service tag
  is not among them

### Requirement: Complete results across pagination
When the platform returns results in pages, the system SHALL follow the
pagination through to exhaustion and return every matching alert. A fetch
SHALL NOT silently return only the first page.

#### Scenario: Matching alerts span several pages
- **WHEN** the alerts matching the scope and time bound span more than one
  page of platform results
- **THEN** the returned alerts include those from every page

### Requirement: No alerts is a valid result
The system SHALL treat "no alerts matched" as a successful, empty result
rather than an error condition — a quiet period is the expected case.

#### Scenario: Nothing fired in the window
- **WHEN** no in-scope alert fired within the requested time bound
- **THEN** the fetch succeeds and yields no alerts

### Requirement: Bounded fetching
Every request the system makes to fetch alerts SHALL be subject to ingestion's
own configured per-request timeout, and a failed request SHALL be retried no
more times than ingestion's own configured retry bound — not the circuit
breaker values that bound investigation.

#### Scenario: Platform does not respond within the timeout
- **WHEN** a request to the platform exceeds the configured per-call timeout
- **THEN** the system abandons that request rather than waiting indefinitely

#### Scenario: Retries are bounded
- **WHEN** requests to the platform keep failing in a retryable way
- **THEN** the system stops after the configured number of retries rather than
  retrying indefinitely

### Requirement: A failed fetch is reported, not disguised
When alerts cannot be retrieved — the platform is unreachable, rejects the
credentials, or keeps failing past the retry bound — the system SHALL raise an
error identifying the failure. It SHALL NOT return an empty or partial set of
alerts, which a caller would be unable to distinguish from a quiet period.

The error SHALL be the one the alert retrieval port declares, whatever the
underlying cause. A caller that handles a failed fetch SHALL NOT have to catch
anything belonging to the platform's client library, and no failure reaching
that caller SHALL depend on which library performed the request — otherwise a
whole class of failure bypasses the caller's handling and is accounted for by
nothing.

#### Scenario: Platform rejects the credentials
- **WHEN** the platform rejects the supplied credentials
- **THEN** the fetch raises an error reporting that the credentials were
  rejected, and no alerts are returned

#### Scenario: Failure part-way through pagination
- **WHEN** the first page of results is retrieved successfully but fetching a
  later page fails past the retry bound
- **THEN** the fetch raises an error rather than returning the pages it
  managed to retrieve

#### Scenario: The platform cannot be reached
- **WHEN** the request never reaches the platform — the host does not resolve,
  the connection is refused, the transport fails, or the retry bound is spent
  without a single answer
- **THEN** the fetch raises the port's own error, identifying the failure and
  the owner whose alerts were being fetched, rather than letting the transport
  failure escape to the caller

#### Scenario: The platform answers with something the client cannot interpret
- **WHEN** the platform's answer reaches the system but its client library
  cannot interpret it as the expected response
- **THEN** the fetch raises the port's own error rather than letting the
  library's own failure escape to the caller

#### Scenario: A failed fetch is accounted for by the run
- **WHEN** a fetch fails for any of the above reasons during a run
- **THEN** the run's own account names the fetch as the stage that failed and
  carries the reason, and the process still finishes unsuccessfully
