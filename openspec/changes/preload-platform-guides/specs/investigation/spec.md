## ADDED Requirements

### Requirement: A specialist is given the platform's guidance for the tools it may reach
Where a provider publishes guides to how its own tools are queried, a
specialist SHALL be given, as part of what it is instructed, every published
guide that concerns a tool its declaration permits. It SHALL NOT be given a
guide that concerns none of its permitted tools, and SHALL NOT be able to list
or load guides for itself while it investigates.

Which guides a specialist is given SHALL follow from the tools its declaration
permits, so that widening or narrowing a specialist's tools changes its
guidance with no further edit. The guides SHALL be the provider's current ones,
obtained from the provider when a run starts, rather than a copy kept by this
project.

A run whose guides cannot be obtained SHALL still investigate, without them,
and SHALL record that it did so. Missing guidance is not a failed retrieval and
SHALL NOT, on its own, mark an investigation incomplete.

#### Scenario: A specialist receives the guide for its tools
- **WHEN** the provider publishes a guide concerning a metric query tool, and a
  specialist's declaration permits that tool
- **THEN** that specialist's instruction contains the guide

#### Scenario: A specialist does not receive a guide for tools it lacks
- **WHEN** the provider publishes a guide concerning only tools a specialist's
  declaration does not permit
- **THEN** that specialist's instruction does not contain the guide

#### Scenario: A specialist cannot browse guides
- **WHEN** a specialist is run against a provider that offers tools for listing
  and loading guides
- **THEN** neither tool is available to it

#### Scenario: A widened declaration brings its guidance with it
- **WHEN** a specialist's declaration is widened to permit a tool covered by a
  guide it was not previously given
- **THEN** it is given that guide, and nothing else is edited to make it so

#### Scenario: Guides cannot be obtained
- **WHEN** the provider cannot be reached for its guides at the start of a run
- **THEN** the run investigates without them, records that the guidance was
  missing, and does not report its investigations as incomplete for that reason
