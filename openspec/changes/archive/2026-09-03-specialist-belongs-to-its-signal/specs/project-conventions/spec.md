## MODIFIED Requirements

### Requirement: Contributors can set up and verify the project from the README

The README SHALL give a contributor an unfamiliar-machine path to a working
environment and a way to confirm the setup succeeded, and SHALL carry the
architecture diagram and the extension guide for adding new adapters.

The extension guide SHALL distinguish the two kinds of extension the project
accepts, because they have different shapes. Adding a notification channel is
implementing a port. Adding observability tooling is declaring specialists of
one's own — what a specialist declaration consists of, which parts are the
contributor's and which are supplied by the deployment, and that one working
specialist is a complete contribution rather than the first of a set that must
all be finished before anything runs.

The guide SHALL locate a specialist's declaration by the crew it joins rather
than by the provider it queries, and SHALL state that each group of tools a
declaration names carries the provider serving it, so that a specialist drawing
on two providers is one declaration in one place. It SHALL state what a
deployment must configure for such a specialist to be offered at all.

The guide SHALL also state what the project cannot check for such a
contribution: nothing verifies that an instruction is any good, which is what
the evaluation harness is for.

The README SHALL name both kinds and point to the guide, which MAY be a
document the README links rather than the README itself — the step-by-step
detail belongs wherever a contributor is sent, not necessarily on the front
page.

#### Scenario: Fresh clone

- **WHEN** a contributor clones the repository and follows the README setup steps
  on a machine with no prior project state
- **THEN** they reach an environment where the documented verification command
  runs the test suite successfully

#### Scenario: Adding a notification channel

- **WHEN** a contributor wants to plug in their own notification tooling
- **THEN** the extension guide tells them which port to implement, where the
  implementation belongs, and what tests it is expected to carry

#### Scenario: Adding observability tooling

- **WHEN** a contributor wants to investigate with their own observability
  platform
- **THEN** the extension guide tells them to declare a specialist — its tools,
  the provider serving each group of them, its instruction, its schema, and its
  signal — that the declaration belongs with the crew rather than under a
  provider's own directory, and what tests it is expected to carry

#### Scenario: One specialist is a complete contribution

- **WHEN** a contributor declares a single specialist for a platform the
  project has never reached
- **THEN** the extension guide makes clear that it runs and contributes
  findings on its own, without any other specialist for that platform
  existing

#### Scenario: A specialist drawing on two providers

- **WHEN** a contributor wants one specialist to draw on two providers
- **THEN** the guide tells them to name the provider on each toolset, and does
  not send them to choose which provider's directory the declaration lives in

#### Scenario: Dependencies are reproducible

- **WHEN** the project's dependencies are installed from the committed lockfile
- **THEN** the resolved versions are identical across machines and in CI
