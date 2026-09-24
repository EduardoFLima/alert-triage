## ADDED Requirements

### Requirement: A specialist is offered the platform's guidance for the tools it may reach
Where a provider publishes guides to how its own tools are queried, a
specialist SHALL be told which of those guides concern a tool its declaration
permits, and SHALL be able to read any of them when it chooses to. It SHALL NOT
be told of, or able to read, a guide that concerns none of its permitted tools,
and SHALL NOT be able to list or load the provider's guides for itself. A
guide's content SHALL reach a specialist only when that specialist asks for it.

Which guides a specialist is offered SHALL follow from the tools its
declaration permits, so that widening or narrowing a specialist's tools changes
its guidance with no further edit. The guides SHALL be obtained from the
provider when a run starts, and SHALL NOT be stored by this project beyond that
run.

Reading a guide SHALL NOT count as a retrieval: it SHALL NOT use the
specialist's tool-call budget, SHALL NOT be citable as evidence, and SHALL NOT
mark an investigation incomplete.

A run whose guides cannot be obtained SHALL still investigate, offering no
guides, and SHALL record that it did so.

#### Scenario: A specialist is offered the guide for its tools
- **WHEN** the provider publishes a guide concerning a metric query tool, and a
  specialist's declaration permits that tool
- **THEN** that specialist is told the guide exists, and its content is not in
  what the specialist was instructed

#### Scenario: A specialist reads an offered guide
- **WHEN** a specialist asks for a guide it was offered
- **THEN** it receives that guide's content, and its tool-call budget is
  unchanged

#### Scenario: A specialist is not offered a guide for tools it lacks
- **WHEN** the provider publishes a guide concerning only tools a specialist's
  declaration does not permit
- **THEN** that specialist is not told of the guide, and asking for it by name
  is refused

#### Scenario: A specialist cannot browse the provider's guides
- **WHEN** a specialist is run against a provider that offers tools for listing
  and loading guides
- **THEN** neither of the provider's tools is available to it

#### Scenario: A widened declaration brings its guidance with it
- **WHEN** a specialist's declaration is widened to permit a tool covered by a
  guide it was not previously offered
- **THEN** it is offered that guide, and nothing else is edited to make it so

#### Scenario: Guides are not kept between runs
- **WHEN** a run ends
- **THEN** nothing it obtained from the provider's guides remains on disk, and
  the next run obtains them again

#### Scenario: Guides cannot be obtained
- **WHEN** the provider cannot be reached for its guides at the start of a run
- **THEN** the run investigates with no guides offered, records that guidance
  was missing, and does not report its investigations as incomplete for that
  reason
