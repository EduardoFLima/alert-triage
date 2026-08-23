## ADDED Requirements

### Requirement: Optional investigation section
The system SHALL treat the `investigation` section of `config.yaml` as
optional and SHALL apply documented defaults for every key it omits, so that a
run investigates without any configuration for it. The section SHALL carry
how an investigation reasons — the model it runs on — and how many attempts an
incident's investigation gets before the system stops retrying it, defaulting
to three. It SHALL NOT carry the location of, or credentials for, any platform
or model provider: those are deployment facts read from the environment only.
A key shaped like one written *into this section* SHALL be refused by name, as
any key the schema has never heard of already is — an operator who typed it
meant something by it, and silently ignoring it would leave them believing a
credential had been supplied. A credential written as its own top-level section
remains inert, exactly as it already is.

The attempt bound SHALL be resolved independently of the `circuit_breakers`
section, which bounds a single call inside one investigation rather than how
many investigations an incident is given.

#### Scenario: Config file omits investigation
- **WHEN** `config.yaml` is present but does not include an `investigation`
  section
- **THEN** the system resolves the investigation settings to their documented
  defaults and proceeds

#### Scenario: The operator chooses a model
- **WHEN** `config.yaml` sets the model under `investigation`
- **THEN** investigations run on that model rather than the default

#### Scenario: Attempts left unconfigured
- **WHEN** the operator sets no attempt bound for investigations
- **THEN** an incident's investigation is attempted up to three times in total

#### Scenario: The operator bounds the attempts
- **WHEN** `config.yaml` sets the attempt bound under `investigation`
- **THEN** an incident's investigation is attempted that many times rather
  than three

#### Scenario: The environment overrides the file
- **WHEN** `config.yaml` sets the model under `investigation` and the
  corresponding environment variable is also set
- **THEN** the environment variable's value wins, as it does for every other
  behavior setting

#### Scenario: A credential written into the section
- **WHEN** `config.yaml` sets a key shaped like a model or platform credential
  under `investigation`
- **THEN** the system refuses to start and names the unrecognised key, rather
  than starting as though a credential had been supplied
