## MODIFIED Requirements

### Requirement: Evidence in a finding is always evidence the platform returned
The evidence carried by a finding SHALL consist only of what the observability
platform actually returned during that investigation. The system SHALL NOT
present as evidence any text produced by the reasoning that formed the
finding, however plausible it looks. Evidence SHALL be identified against what
was retrieved and reproduced from the retrieved result, so that a fabricated
or mistaken reference cannot be rendered into a report.

Evidence SHALL be identifiable at two grains: the retrieval as a whole, and an
individual item within it. A finding about a pattern cites the items showing
it; a finding about something with no discrete items — an aggregate, a
dependency map, a waterfall — cites the retrieval. A finding citing neither
SHALL be discarded.

The grain evidence is cited at SHALL be decided by what was retrieved and not
by how the platform chose to encode it. A platform may answer with structured
data or with a block of text carrying a table of rows; a result that holds
discrete things SHALL yield them either way. A retrieval that does hold
discrete things and is cited only as a whole is a loss of precision the system
SHALL NOT accept as the platform's answer being an aggregate.

Every retrieved item SHALL be rendered into a report through one common
normalisation — an identifier, the instant it concerns, a human-readable
summary, and an address at which a human can open the thing itself on the
platform, alongside what the platform actually returned — rather than through
a translation written per tool, so that a specialist reaching a new tool needs
no new rendering.

An item's address SHALL be derived from what was retrieved, never produced by
the reasoning that formed the finding. The system SHALL NOT accept an address
as part of what a specialist reports, because an invented address cannot be
checked against what was retrieved the way an invented identifier can, and a
reader will follow it. An address SHALL be absent where the platform offers no
way to address that item, which is a complete answer rather than a failure:
evidence without an address is still evidence, and the system SHALL render it
as such.

An address SHALL be available at both grains at which evidence is identified.
An individual item SHALL be addressed as that item where the retrieved result
identifies it, and a retrieval SHALL be addressed as the query that produced
it over the window it ran over, so that evidence with no discrete items is
still something a reader can go and look at.

Where the platform returns an address alongside what it retrieved, that
address SHALL be preferred to one the system composed. The platform ran the
view and can name it exactly; the system can only infer it from which tool was
called and what it was called with, and an inferred address that opens a
different view of the same subject is the failure the system is trying to
avoid. An address the platform returns SHALL be subject to the same rule as
any other: it is part of what was retrieved, never part of what a specialist
reported.

A finding whose evidence cannot be traced back to what was retrieved SHALL be
discarded, and the system SHALL record that it was discarded and why, so that
fabrication is visible to whoever is tuning the investigation. Discarding one
finding SHALL NOT discard the others, and SHALL NOT fail the investigation:
findings whose evidence checks out SHALL still be reported. An investigation
left with no findings after discarding SHALL return an empty result — an
honest "nothing notable" — rather than a failure, because the investigation
did run.

This requirement constrains evidence, not description. How a finding
characterises its evidence — a rate, a count, a description of a pattern —
remains the investigation's own account of what it saw, which is why the
examples travel with it for a human to check it against.

#### Scenario: Evidence names something that was never retrieved
- **WHEN** a finding's evidence refers to a retrieval or an item the platform
  did not return during the investigation
- **THEN** the finding is discarded, the discard is recorded, and it does not
  appear in any report

#### Scenario: A finding about an aggregate
- **WHEN** a finding concerns a result with no discrete items in it
- **THEN** it cites the retrieval that produced it, and is kept

#### Scenario: A finding citing nothing
- **WHEN** a finding cites neither a retrieval nor an item within one
- **THEN** it is discarded

#### Scenario: One bad finding among good ones
- **WHEN** an investigation produces three findings and only one has evidence
  that cannot be traced to what was retrieved
- **THEN** the other two are returned and reported, and the investigation is
  not treated as a failure

#### Scenario: Nothing survives the check
- **WHEN** every finding an investigation produced has untraceable evidence
- **THEN** the investigation returns no findings, which is reported as nothing
  notable rather than as a failed investigation

#### Scenario: Evidence is reproduced, not restated
- **WHEN** a finding's evidence is presented to a human
- **THEN** what they read is the retrieved result itself, not a retelling of it

#### Scenario: Evidence from a tool nobody anticipated
- **WHEN** a specialist gathers evidence from a tool the system carries no
  per-tool handling for
- **THEN** that evidence is identified, checked, and rendered like any other

#### Scenario: A retrieval answered as a table of text
- **WHEN** the platform answers a retrieval with text carrying a header row
  and rows beneath it, rather than with structured data
- **THEN** each row is identified as an item within that retrieval, and is
  summarised from the row rather than from any preamble describing the answer

#### Scenario: An answer in text that holds no table
- **WHEN** the platform answers a retrieval with text that carries no rows
- **THEN** the retrieval is citable as a whole and carries no items, as any
  result with nothing discrete in it does

#### Scenario: Evidence carries where to go and see it
- **WHEN** a retrieved item is presented to a human and the platform can
  address it
- **THEN** the item carries an address that opens that item on the platform,
  distinct from the summary of what it says

#### Scenario: An item the platform cannot address
- **WHEN** a retrieved item is presented to a human and the platform offers no
  way to address it
- **THEN** the item carries no address, and is still reported with its
  identifier, instant, and summary

#### Scenario: An address is never taken from what a specialist reports
- **WHEN** a specialist's report includes something shaped like an address for
  its evidence
- **THEN** it is not used, and the address a reader is given is the one derived
  from what was retrieved

#### Scenario: An aggregate is addressable
- **WHEN** a finding cites a retrieval that produced no discrete items
- **THEN** the address a reader is given opens the query that produced it over
  the window it ran over

#### Scenario: The platform addressed its own answer
- **WHEN** a retrieval comes back carrying an address the platform composed for
  the view it ran
- **THEN** that address is the one a reader is given, in place of the one the
  system would have composed from the tool and its arguments

#### Scenario: The platform addressed nothing
- **WHEN** a retrieval comes back with no address of the platform's own
- **THEN** the address a reader is given is the one the system composes, as
  before
