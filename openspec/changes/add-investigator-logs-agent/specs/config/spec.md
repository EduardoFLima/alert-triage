## ADDED Requirements

### Requirement: Optional investigation section
The system SHALL treat the `investigation` section of `config.yaml` as
optional and SHALL apply documented defaults for every key it omits, so that a
run investigates without any configuration for it. The section SHALL carry
how an investigation reasons — the model it runs on — and SHALL NOT carry the
location of, or credentials for, any platform or model provider: those are
deployment facts read from the environment only, and a key shaped like one
written into this section SHALL be inert.

#### Scenario: Config file omits investigation
- **WHEN** `config.yaml` is present but does not include an `investigation`
  section
- **THEN** the system resolves the investigation settings to their documented
  defaults and proceeds

#### Scenario: The operator chooses a model
- **WHEN** `config.yaml` sets the model under `investigation`
- **THEN** investigations run on that model rather than the default

#### Scenario: The environment overrides the file
- **WHEN** `config.yaml` sets the model under `investigation` and the
  corresponding environment variable is also set
- **THEN** the environment variable's value wins, as it does for every other
  behavior setting

#### Scenario: A credential written into the section
- **WHEN** `config.yaml` sets a key shaped like a model or platform credential
  under `investigation`
- **THEN** it is not used to authenticate anything, and resolution proceeds as
  if it were absent
