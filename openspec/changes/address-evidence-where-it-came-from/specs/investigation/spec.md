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
identifies it, and a retrieval SHALL be addressed as whatever produced it —
the search, the query, or the view it came from — over the window it ran over,
so that evidence with no discrete items is still something a reader can go and
look at.

An address SHALL open the retrieval it was built for. What produced a
retrieval depends on which tool was called, so the address SHALL be derived
from the tool as well as from what the tool was asked, and the system SHALL
NOT address a retrieval as a kind of thing it did not come from. Where the
platform's address for a retrieval of that kind is not known, the evidence
SHALL carry no address: absence is alre, and anady a complete answer here
address that opens the wrong view is worse than none, because a reader cannot
tell it from a view that is genuinely empty.

A finding MAY name which section of an address it concerns, chosen from a set
the system enumerates. This is the only part of an address the reasoning
contributes, and it is admissible where a written address is not because a
choice from a closed set can be checked against that set, and a choice outside
it is rejected rather than followed. The system SHALL compose the address
itself — its host, its path, the service and the window it scopes to — and
SHALL treat an absent or unrecognised section as no section, landing a reader
on the address without it.

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
- **THEN** the address a reader is given opens whatever produced that
  retrieval, over the window it ran over

#### Scenario: Two retrievals from different kinds of tool
- **WHEN** one finding cites a retrieval of the service's logs and another
  cites a retrieval of its resource metrics
- **THEN** each address opens the view its own retrieval came from, and
  neither opens the other's

#### Scenario: A finding names the section it concerns
- **WHEN** a finding names a section from the enumerated set
- **THEN** the address a reader is given opens on that section of the page the
  system composed, and no part of that address but the section came from the
  finding

#### Scenario: A finding names a section that is not one of them
- **WHEN** a finding names a section outside the enumerated set
- **THEN** it is ignored, and the reader is given the same address without a
  section rather than one built around a section that does not exist

#### Scenario: A retrieval the platform's address form is unknown for
- **WHEN** a specialist retrieves evidence from a tool the system has no
  address form for
- **THEN** the evidence carries no address, and is reported with its
  identifier, instant, and summary as evidence the platform cannot be opened at
