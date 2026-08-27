## MODIFIED Requirements

### Requirement: Platform connection settings come from the environment
The system SHALL resolve the Datadog site and API credentials from the
environment only, using the platform's own conventional variable names rather
than the `section.key` mapping used for behavior settings. The site SHALL fall
back to a documented default when unset, so a deployment against the default
Datadog region need set only credentials. Credentials have no default and
SHALL be reported as required when absent.

Where the platform serves the pages a reader opens SHALL also be resolvable
from the environment, falling back to a documented default. An organisation
issued a sub-domain of its own serves those pages only there, and a link built
for the default host reaches nobody on such an account. This setting SHALL
affect only the addresses a human is sent to: the hosts the system itself
reaches — the API and the tool server — SHALL be unaffected by it.

#### Scenario: Site left unset
- **WHEN** the Datadog site environment variable is not set
- **THEN** the system resolves the site to the documented default

#### Scenario: Site set for a different region
- **WHEN** the Datadog site environment variable names a non-default region
- **THEN** the system reaches the platform at that region

#### Scenario: Credentials present in the environment
- **WHEN** the Datadog API credential environment variables are set
- **THEN** the system uses them to authenticate against the platform

#### Scenario: Credentials missing entirely
- **WHEN** the Datadog API credential environment variables are not set
- **THEN** the system reports that the credentials are required, rather than
  attempting an unauthenticated call

#### Scenario: The web host is left unset
- **WHEN** the web sub-domain environment variable is not set
- **THEN** links are built for the documented default host over the resolved
  region

#### Scenario: An organisation on its own sub-domain
- **WHEN** the web sub-domain environment variable names a sub-domain of its
  own
- **THEN** every link a reader is given addresses that sub-domain, and the
  hosts the system itself reaches are unchanged
