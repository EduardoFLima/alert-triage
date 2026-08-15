## Purpose

Gets a triage report out of the process and in front of the team: what a report
carries, how a channel is expected to deliver it, and what it means for
delivery to have succeeded when a report goes to more than one channel at once.

## Requirements

### Requirement: A triage report is channel-neutral
A triage report SHALL carry the identity of the incident it concerns, a
single-line subject, and a body of plain text, and SHALL NOT carry any
channel's formatting. Rendering a report into the shape one channel expects
SHALL be that channel's own work, so that adding a channel changes nothing
about what a report is, and changing what a report says changes nothing about
how any channel delivers it.

#### Scenario: One report reaches two channels
- **WHEN** a report is delivered to an email channel and a chat channel at once
- **THEN** both receive the same subject and body, each rendered in the form
  its own medium expects, and neither renders anything the other has to know
  about

#### Scenario: A report identifies its incident
- **WHEN** a report is delivered
- **THEN** it carries the identifier of the incident it concerns, so a human
  and a later slice can tell two reports about different incidents apart

#### Scenario: The body is opaque to delivery
- **WHEN** the body of a report changes
- **THEN** every channel delivers the new body unchanged, without any channel
  needing to be adjusted

### Requirement: A channel delivers a report or reports its failure
A notification channel SHALL accept one report at a time and either deliver it
to its destination or raise a delivery failure. It SHALL NOT report success
when the destination did not accept the report, and SHALL NOT swallow a
transport error and return quietly.

#### Scenario: The destination accepts the report
- **WHEN** a channel delivers a report and its destination accepts it
- **THEN** the channel reports success

#### Scenario: The destination is unreachable
- **WHEN** a channel cannot reach its destination
- **THEN** the channel raises a delivery failure rather than returning as if
  the report had been sent

#### Scenario: The destination rejects the report
- **WHEN** a channel reaches its destination and the destination refuses the
  report — rejecting the sender, the recipient, or the payload
- **THEN** the channel raises a delivery failure naming what was refused

#### Scenario: A delivery failure is recognisable without knowing the channel
- **WHEN** a caller handles a delivery failure
- **THEN** it can do so without knowing which channel raised it or importing
  anything specific to that channel

### Requirement: Email delivery
The system SHALL provide a channel that delivers a report as an email message,
with the report's subject as the message's subject and its body as the message
body, sent from the configured sender to every configured recipient.

#### Scenario: A report is emailed
- **WHEN** a report is delivered to the email channel
- **THEN** an email carrying the report's subject and body is submitted for
  delivery to each configured recipient

#### Scenario: The mail server refuses the message
- **WHEN** the mail server rejects the message or cannot be reached
- **THEN** the channel raises a delivery failure

### Requirement: Microsoft Teams delivery
The system SHALL provide a channel that delivers a report to a Microsoft Teams
destination through the incoming-webhook mechanism Teams currently supports,
presenting the report's subject and body as a message a human reads in the
channel.

#### Scenario: A report reaches a Teams channel
- **WHEN** a report is delivered to the Teams channel
- **THEN** a message carrying the report's subject and body is posted to the
  configured Teams destination

#### Scenario: Teams rejects the post
- **WHEN** the Teams destination responds with a failure, or cannot be reached
- **THEN** the channel raises a delivery failure carrying what the destination
  said

### Requirement: One failing channel does not suppress another
When more than one channel is configured, the system SHALL attempt delivery on
every one of them, regardless of any other channel's outcome. A channel that
fails SHALL NOT prevent a channel that has not been tried yet from being tried,
and SHALL NOT undo a delivery that already succeeded.

#### Scenario: The first channel fails
- **WHEN** two channels are configured and the first one attempted fails
- **THEN** the system still attempts the second, and the report is delivered
  there

#### Scenario: Every channel is attempted
- **WHEN** several channels are configured and one of them fails
- **THEN** every configured channel has been attempted exactly once

#### Scenario: A failure that reached nobody is not hidden
- **WHEN** a channel fails while another succeeds
- **THEN** the failure is surfaced for an operator to see, rather than being
  discarded because the report got through elsewhere

### Requirement: Delivery has failed only when no channel accepted the report
The system SHALL treat delivery as successful when at least one configured
channel accepted the report, and SHALL raise a delivery failure only when every
configured channel failed. The failure SHALL account for every channel that was
attempted, so that an operator learns what went wrong on each rather than only
on the last.

#### Scenario: Partial delivery is a success
- **WHEN** one of two configured channels accepts the report and the other
  fails
- **THEN** delivery succeeds, because the team has been told

#### Scenario: No channel accepts the report
- **WHEN** every configured channel fails
- **THEN** the system raises a delivery failure

#### Scenario: The failure accounts for every channel
- **WHEN** delivery fails because every channel failed
- **THEN** the raised failure describes each channel's failure, not just the
  last one attempted

### Requirement: A report is attempted once per run
The system SHALL attempt each channel exactly once for a given report and SHALL
NOT retry a failed delivery within the run that produced it. The outcome it
raises or returns SHALL be enough for a caller to decide whether the incident
was reported, so that a report nobody received is attempted again by a later
run rather than starting a cooldown on a delivery that did not happen.

#### Scenario: A failing channel is not retried in place
- **WHEN** a channel fails to deliver a report
- **THEN** the system moves on to the remaining channels without retrying that
  one, and the run does not stall on it

#### Scenario: The outcome is decidable by the caller
- **WHEN** delivery of a report finishes, in success or in failure
- **THEN** a caller can tell from the outcome alone whether any channel
  accepted the report, without inspecting individual channels
