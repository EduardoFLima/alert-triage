## ADDED Requirements

### Requirement: A toolset names the provider that serves it
Each group of tools a specialist may reach SHALL name the provider serving that
group, alongside the group's own name and the tools within it permitted to this
specialist. A specialist's toolsets SHALL be allowed to name different
providers, so that one specialist may draw on more than one provider without
ceasing to be a single declaration.

A specialist SHALL remain platform-*specific* in what it asks: its tool names
and its query dialect do not translate, and naming a provider does not make a
declaration portable between providers. What ceases to be true is that a
specialist belongs to exactly one provider.

Which provider serves a toolset SHALL be part of the declaration; where that
provider is and what authenticates against it SHALL NOT be.

#### Scenario: A specialist draws on two providers
- **WHEN** a specialist declares one toolset served by one provider and another
  toolset served by a second
- **THEN** it reaches the tools it named on each provider, each through that
  provider's own location and credentials, within a single investigation

#### Scenario: A toolset naming no provider
- **WHEN** a toolset is declared without naming the provider that serves it
- **THEN** the declaration is refused, rather than being resolved against
  whichever provider a deployment happens to configure first

#### Scenario: Reaching a second provider changes no caller
- **WHEN** an existing specialist is widened to reach a second provider
- **THEN** only that specialist's declaration changes, and no other specialist,
  no caller, and no other provider's specialists change with it

### Requirement: A deployment offers only the specialists whose providers it configured
The system SHALL offer a specialist for consultation only where the deployment
has configured every provider that specialist's toolsets name. A specialist
naming a provider the deployment did not configure SHALL NOT be offered, and
SHALL NOT be presented as a specialist that was available and went unconsulted.

This is what keeps a signal from being consulted twice once two providers can
serve the same one: a deployment holding credentials for a single provider
offers a single specialist per signal without naming any of them.

A deployment that configures no provider at all SHALL refuse to start rather
than run an investigation with an empty crew.

#### Scenario: One provider configured, two declared
- **WHEN** two specialists cover the same signal against different providers and
  the deployment configures only one of those providers
- **THEN** only that provider's specialist is offered, and the signal is
  consulted at most once

#### Scenario: Both providers configured
- **WHEN** the deployment configures both providers
- **THEN** both specialists are offered, and which of them an incident needs is
  decided per incident like any other choice between specialists

#### Scenario: A specialist reaching an unconfigured provider
- **WHEN** a specialist's toolsets name two providers and the deployment
  configures only one
- **THEN** that specialist is not offered, rather than being run against half
  the evidence it was declared to gather

#### Scenario: No provider configured
- **WHEN** the deployment configures no observability provider
- **THEN** the run refuses to start and names what is missing, without fetching
  any alerts

## MODIFIED Requirements

### Requirement: A specialist is a declaration that owns what it may ask
A specialist SHALL be declared as a whole: the signal it reports under, what
it is instructed to look for, the shape of what it reports, the tools it is
permitted to reach and the provider serving each group of them, and — where it
differs from the default — the model it reasons on. What a specialist is
permitted to ask SHALL be part of that declaration rather than an operator
setting, because an instruction assumes the tools it was written against and
the two cannot be tuned apart.

Adding a specialist, or changing which tools an existing one may reach, SHALL
be an edit to that specialist's declaration alone, and SHALL NOT change the
component that runs the crew, the caller that requests an investigation, or
any other specialist. A specialist SHALL be able to reason on a different
model from its siblings without being a special case.

A declaration SHALL be located by the crew it belongs to rather than by the
provider it queries, so that a specialist drawing on two providers has one
home rather than a choice of two.

Deployment facts — where each provider is, how to authenticate against each,
and the model every specialist runs on unless it says otherwise — SHALL be
supplied to a declaration rather than written into it.

#### Scenario: A specialist's tools change
- **WHEN** the tools one specialist is permitted to reach are widened
- **THEN** only that specialist's declaration changes, and no other specialist
  and no caller changes with it

#### Scenario: A specialist reasons on its own model
- **WHEN** one specialist is configured to run on a different model from the
  default
- **THEN** it reasons on that model and every other specialist reasons on the
  default

#### Scenario: A specialist may not reach a tool it did not declare
- **WHEN** a specialist is run against a platform offering many tools
- **THEN** the tools available to it are the ones its declaration names, and no
  others

#### Scenario: Deployment facts are supplied, not declared
- **WHEN** the same specialist is run against a different platform account
- **THEN** its declaration is unchanged, and only what was supplied to it
  differs

#### Scenario: A declaration is found by its crew
- **WHEN** a contributor looks for a specialist's declaration
- **THEN** they find it with the rest of the crew, whichever providers it
  happens to query

### Requirement: Investigation credentials and endpoints come from the environment
Each observability provider's location and credentials SHALL be read from the
environment, using that provider's own conventional variable names, and SHALL
NOT be configurable in `config.yaml`. A deployment reaching more than one
provider SHALL configure each independently, so that adding a provider is
adding its environment values rather than changing how any other provider is
reached. The model an investigation runs on SHALL be a behavior setting
resolved like every other, while the credential that model needs SHALL be an
environment-only deployment fact. That credential, and which model platform it
authenticates against, SHALL be resolved from the run's environment and
supplied to the model, rather than left for the model's own client to discover.
The system SHALL refuse to start when a credential an investigation needs is
absent, rather than failing part-way through a run.

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

#### Scenario: A second provider is configured
- **WHEN** the environment supplies a second provider's location and
  credentials
- **THEN** the specialists naming that provider become available, and how the
  first provider is reached is unchanged

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
