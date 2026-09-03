## MODIFIED Requirements

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
