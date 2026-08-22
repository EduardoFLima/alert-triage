## ADDED Requirements

### Requirement: One resolved environment, read by everything
A run SHALL resolve its environment once, from the process environment
supplemented by an optional file beside the run, and every setting and
credential the run uses SHALL be read from that resolved environment. A name
the process exported SHALL win over the same name in the file, so a container
or scheduler is never overridden by a file lying beside it. No part of the
system SHALL read the process environment behind the resolved one: a name the
file supplies SHALL behave exactly as though it had been exported, including
where the setting is consumed by a vendor library rather than by this system's
own code.

#### Scenario: A value supplied only by the file
- **WHEN** a setting or credential is declared in the file and not exported by
  the process
- **THEN** the run behaves exactly as it would had the operator exported that
  name, whichever component consumes it

#### Scenario: The process disagrees with the file
- **WHEN** the same name is exported by the process and declared in the file
- **THEN** the run uses the exported value

#### Scenario: No file is present
- **WHEN** the file is absent
- **THEN** the run resolves entirely from the process environment and reports
  no error for the missing file

#### Scenario: A name the file only mentions
- **WHEN** the file names a variable without giving it a value
- **THEN** it does not shadow the same name exported by the process
