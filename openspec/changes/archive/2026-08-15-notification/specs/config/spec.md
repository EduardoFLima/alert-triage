## ADDED Requirements

### Requirement: Notification channel settings come from the environment
Where a report is sent and how to authenticate to get it there is a deployment
fact, not triage behavior: a mail server, a sender, a recipient list, and a
webhook URL all change when the same triage behavior runs for a different team
or from a different environment, while what the system watches and how it
groups stay identical. The system SHALL resolve every notification channel's
settings from the environment only, and SHALL NOT read them from `config.yaml`.
A channel setting written into `config.yaml` SHALL be inert, exactly as a
credential written there already is.

#### Scenario: Channel settings supplied by the environment
- **WHEN** the environment supplies a channel's settings
- **THEN** the system delivers reports through that channel using them

#### Scenario: Channel settings written into the config file
- **WHEN** `config.yaml` contains keys naming a mail server, a recipient, or a
  webhook URL
- **THEN** the system does not use them, and resolves the channel's settings
  from the environment as if the keys were absent

#### Scenario: A webhook URL is never a config file key
- **WHEN** an operator looks for a place to record a webhook URL
- **THEN** there is no `config.yaml` key for it, so a file shared between
  deployments cannot carry one deployment's destination

### Requirement: The environment decides which channels are active
The system SHALL treat a channel as active when the environment supplies the
settings that channel requires, and inactive when it does not. An inactive
channel SHALL take no part in delivery and SHALL NOT cause a failure by being
absent. A channel whose settings are supplied only in part SHALL be reported as
a configuration error rather than silently ignored, since a half-configured
channel is a mistake, not a decision.

#### Scenario: Only one channel configured
- **WHEN** the environment configures one channel and says nothing about the
  other
- **THEN** the system delivers through the configured channel alone, and the
  absence of the other is not an error

#### Scenario: Both channels configured
- **WHEN** the environment configures both channels
- **THEN** the system delivers through both

#### Scenario: A channel configured only in part
- **WHEN** the environment supplies some but not all of a channel's required
  settings
- **THEN** the system refuses to start, naming the missing setting

### Requirement: A deployment with no notification channel refuses to start
The system SHALL refuse to start when the environment configures no
notification channel at all. A run that can investigate but can tell nobody
what it found has no reason to run, and failing at startup makes that visible
immediately rather than at the moment a report was due.

#### Scenario: No channel configured
- **WHEN** the environment configures neither the email channel nor the Teams
  channel
- **THEN** the system refuses to start, saying that at least one notification
  channel must be configured

#### Scenario: The refusal is a configuration error like any other
- **WHEN** the system refuses to start for want of a channel
- **THEN** it fails the same way it fails for a missing mandatory scope or a
  missing credential, rather than in a manner particular to notification
