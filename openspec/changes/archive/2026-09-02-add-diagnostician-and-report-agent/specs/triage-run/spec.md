## MODIFIED Requirements

### Requirement: The report a run sends
A run SHALL build each report from the incident and its investigation. The
report SHALL name the incident's service in its subject, and its body SHALL
carry what the investigation concluded, what it found with the evidence behind
it, and the alerts absorbed into the incident — when they fired, their titles,
and the links back to the platform that reported them.

A report of a concluded investigation SHALL state the hypothesis and the
confidence level the investigation attached to it, and SHALL present both as
what they are: a first-pass conclusion offered for a human to act on or
disagree with, never a verdict and never an instruction. The report SHALL NOT
present a hypothesis the investigation did not produce, and SHALL NOT state a
confidence level of its own.

The hypothesis SHALL NOT displace what it was drawn from. A report carrying a
conclusion SHALL still carry the findings and the evidence beneath them, so
that a reader can check the conclusion rather than take it.

Evidence in a report SHALL carry its own link back to the platform, where the
evidence has one, so that a reader who wants to see a finding for themselves
can go from the report to the thing it rests on. A link SHALL be rendered as
an address standing on its own, distinct from the text of what was retrieved,
so that a channel which turns addresses into links finds a whole one and a
channel which does not still shows a reader something they can copy. The
system SHALL NOT render a link inside a passage of text that is subject to
truncation, because a truncated address is worse than none: it still reads as
a link and leads somewhere the evidence is not.

When the investigation behind a report could not gather all the evidence it
asked for, the report SHALL say so, so that a reader can tell findings drawn
from everything the platform holds from findings drawn from part of it. A
report SHALL NOT present a partially evidenced investigation as a complete
one.

When no findings are available because every investigation of the incident
failed, the report SHALL carry the alerts as above and SHALL state plainly
that investigation was attempted and could not complete, rather than
presenting itself as triage. Such a report SHALL carry no hypothesis and no
confidence level, because no investigation produced one.

#### Scenario: A report identifies its service and alerts
- **WHEN** a report is built for an incident with three alerts
- **THEN** its subject names the service and its body lists all three alerts
  with their times and links

#### Scenario: A report carries what was found
- **WHEN** an investigation returned findings for an incident
- **THEN** the report's body states those findings and the evidence behind
  them

#### Scenario: A report carries what was concluded
- **WHEN** an investigation returned a hypothesis and a confidence level
- **THEN** the report's body states both, and states them as a hypothesis
  rather than as a verdict or an instruction

#### Scenario: The report does not pretend to conclude
- **WHEN** a report is built from an investigation that produced a hypothesis
- **THEN** its body presents the hypothesis and its confidence level as a
  first-pass conclusion offered for a human to judge or disagree with, and
  recommends no action and takes none

#### Scenario: The conclusion does not replace the evidence
- **WHEN** a report carries a hypothesis
- **THEN** it also carries the findings and evidence the hypothesis was drawn
  from

#### Scenario: An investigation that concluded nothing
- **WHEN** an investigation completed but produced no hypothesis
- **THEN** the report carries its findings and evidence and states no
  hypothesis, rather than one the report composed

#### Scenario: Evidence in a report can be followed
- **WHEN** a report is built from findings whose evidence carries links
- **THEN** each such piece of evidence appears with its link, and a reader can
  follow it to that evidence on the platform

#### Scenario: Evidence with no link is still reported
- **WHEN** a report is built from findings whose evidence carries no link
- **THEN** that evidence appears with its time and summary as before, and the
  report notes no absence

#### Scenario: A link is never truncated
- **WHEN** a piece of evidence carries a link and a long summary
- **THEN** the summary may be shortened and the link is rendered whole

#### Scenario: The report does not pretend to be triage
- **WHEN** a report is built for an incident whose investigations all failed
- **THEN** its body says investigation was attempted and could not complete,
  and carries no hypothesis and no confidence level

#### Scenario: The report does not pretend to be complete
- **WHEN** a report is built from findings whose investigation could not
  gather part of its evidence
- **THEN** its body says the evidence gathered was incomplete, alongside the
  findings it did produce

#### Scenario: A complete investigation reads as one
- **WHEN** a report is built from findings whose investigation gathered
  everything it asked for
- **THEN** its body carries no incompleteness note, whether or not the
  findings were notable

#### Scenario: Report content is replaceable
- **WHEN** the way a report's body is produced changes
- **THEN** neither the run's ordering nor any notification channel changes
  with it

### Requirement: A report says which signals were examined
A report SHALL make plain which observability signals the investigation behind
it actually consulted, so that a reader can tell what was covered from what was
not. A report SHALL NOT name one signal when several were consulted, nor imply
coverage of a signal no specialist looked at.

What a report claims SHALL be what the investigation did, not what the
deployment could have done. A signal a specialist exists for but was not
consulted about SHALL NOT be named as examined, because an investigation that
chose not to look at a signal and one that looked and found it clean are
opposite pieces of news.

This matters most where nothing was found. "Nothing notable" is only
interpretable against a scope: a reader told the logs were clean draws a
different conclusion from one told the logs, the golden signals, the traces and
the infrastructure were all clean, and the report SHALL NOT leave them guessing
which they were told.

An investigation that consulted no signal at all SHALL be reported as such, and
SHALL NOT be reported as one that found nothing notable.

#### Scenario: Nothing notable across several signals
- **WHEN** an investigation consults several specialists and finds nothing
  notable in any of them
- **THEN** the report says nothing notable was found and names the signals that
  were consulted, rather than naming one of them

#### Scenario: A signal that was not consulted
- **WHEN** an investigation consults two of the four declared specialists and
  finds nothing notable
- **THEN** the report names those two signals as examined and does not present
  the other two as clean

#### Scenario: Findings name the signal they came from
- **WHEN** a report carries findings drawn from more than one signal
- **THEN** each finding is attributed to the signal it was drawn from

#### Scenario: No signal was consulted
- **WHEN** an investigation completes having consulted no specialist
- **THEN** the report says no signal was examined, rather than saying nothing
  notable was found

#### Scenario: The wording survives a specialist being added
- **WHEN** a further specialist joins the crew
- **THEN** the report's account of what was examined still names exactly the
  signals that were consulted, and no report claims a scope wider than what ran
