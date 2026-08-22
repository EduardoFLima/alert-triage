## MODIFIED Requirements

### Requirement: Investigation credentials and endpoints come from the environment
The observability platform's location and credentials SHALL be read from the
environment, using the platform's own conventional variable names, and SHALL
NOT be configurable in `config.yaml`. The model an investigation runs on
SHALL be a behavior setting resolved like every other, while the credential
that model needs SHALL be an environment-only deployment fact. That credential,
and which model platform it authenticates against, SHALL be resolved from the
run's environment and supplied to the model, rather than left for the model's
own client to discover. The system SHALL refuse to start when a credential an
investigation needs is absent, rather than failing part-way through a run.

#### Scenario: A credential is missing
- **WHEN** the environment does not supply a credential an investigation
  requires
- **THEN** the system refuses to start and names what is missing, without
  fetching any alerts

#### Scenario: A credential written into the config file
- **WHEN** `config.yaml` contains a key shaped like a platform credential
- **THEN** it is not used to reach the platform, and resolution proceeds as if
  it were absent

#### Scenario: The same behavior against another account
- **WHEN** the same `config.yaml` is deployed against a different platform
  account
- **THEN** only environment values change

#### Scenario: A credential the process never exported
- **WHEN** the model's credential reaches the run's environment without being
  exported by the process
- **THEN** investigations authenticate with it, rather than the model behaving
  as though no credential were configured

#### Scenario: A start that would not have authenticated
- **WHEN** the system starts rather than refusing
- **THEN** the credential it accepted is the one an investigation's model will
  actually use, so a run never passes its startup check and then fails to
  authenticate on its first incident

## ADDED Requirements

### Requirement: The model platform an investigation authenticates against
A deployment SHALL choose, through the environment, whether an investigation's
model is reached with an API key or against an enterprise model platform using
the credentials that deployment already holds. The choice SHALL be made from
the run's resolved environment, under the model SDK's own conventional
variable names, and SHALL determine how the model is reached. A deployment
that names an enterprise project and location SHALL have them used; one that
names neither SHALL fall back to whatever that platform's own credential
discovery provides.

#### Scenario: An API key deployment
- **WHEN** the environment supplies an API key and does not select an
  enterprise platform
- **THEN** investigations reason through the key, and no enterprise project or
  location is required

#### Scenario: An enterprise deployment
- **WHEN** the environment selects the enterprise platform
- **THEN** investigations reason against that platform, and the run does not
  refuse for having no API key

#### Scenario: An enterprise deployment naming its project
- **WHEN** the environment selects the enterprise platform and names a project
  and location
- **THEN** investigations are made against that project and location

#### Scenario: Neither is configured
- **WHEN** the environment supplies no API key and selects no enterprise
  platform
- **THEN** the run refuses to start and names both ways of configuring it
