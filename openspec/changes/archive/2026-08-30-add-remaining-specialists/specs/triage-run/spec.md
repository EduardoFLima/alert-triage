## ADDED Requirements

### Requirement: A report says which signals were examined
A report SHALL make plain which observability signals the investigation behind
it examined, so that a reader can tell what was covered from what was not. A
report SHALL NOT name one signal when several were examined, nor imply coverage
of a signal no specialist looked at.

This matters most where nothing was found. "Nothing notable" is only
interpretable against a scope: a reader told the logs were clean draws a
different conclusion from one told the logs, the golden signals, the traces and
the infrastructure were all clean, and the report SHALL NOT leave them guessing
which they were told.

#### Scenario: Nothing notable across several signals
- **WHEN** an investigation examines several signals and finds nothing notable
  in any of them
- **THEN** the report says nothing notable was found and names the signals that
  were examined, rather than naming one of them

#### Scenario: Findings name the signal they came from
- **WHEN** a report carries findings drawn from more than one signal
- **THEN** each finding is attributed to the signal it was drawn from

#### Scenario: The wording survives a specialist being added
- **WHEN** a further specialist joins the crew
- **THEN** the report's account of what was examined widens with it, and no
  report claims a scope that no longer matches what ran
