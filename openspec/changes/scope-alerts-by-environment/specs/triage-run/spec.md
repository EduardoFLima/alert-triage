## ADDED Requirements

### Requirement: A report names the environment of its incident
A report SHALL name the environment its incident was observed in, alongside
the service, in its subject and its body, so that a reader receiving reports
from more than one deployment can tell production from anything else without
opening a link.

#### Scenario: A production incident's report
- **WHEN** a run scoped to `prod` reports an incident on `checkout`
- **THEN** the report's subject and body name both `checkout` and `prod`

#### Scenario: Two deployments, one service
- **WHEN** one deployment scoped to `prod` and another scoped to `staging` each
  report an incident on `checkout`
- **THEN** the two reports are distinguishable by environment from their
  subjects alone
