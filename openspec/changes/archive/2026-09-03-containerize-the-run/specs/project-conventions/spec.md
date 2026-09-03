## MODIFIED Requirements

### Requirement: Quality gate runs on every change

Lint, formatting, static type checking, the full test suite, and the build of
the distributable image SHALL run automatically on pushes and pull requests. A
failure in any of them SHALL fail the overall check.

#### Scenario: Change violates lint or formatting rules

- **WHEN** a pull request contains code that fails lint or is not formatted to
  the project style
- **THEN** the gate reports failure and identifies the rule and location

#### Scenario: Change breaks type checking

- **WHEN** a pull request introduces a type error under the project's strict
  type-checking settings
- **THEN** the gate reports failure and identifies the offending expression

#### Scenario: Change breaks a test

- **WHEN** a pull request causes any test, including the architecture check, to
  fail
- **THEN** the gate reports failure and surfaces the failing test output

#### Scenario: Change breaks the image build

- **WHEN** a pull request leaves the distributable image unable to build
- **THEN** the gate reports failure and surfaces the failing build step, rather
  than passing on checks that never built it

#### Scenario: Change passes every check

- **WHEN** a pull request passes lint, formatting, type checking, all tests, and
  the image build
- **THEN** the gate reports success

### Requirement: Contributors can set up and verify the project from the README

The README SHALL give a contributor an unfamiliar-machine path to a working
environment and a way to confirm the setup succeeded, and SHALL carry the
architecture diagram and the extension guide for adding new adapters.

The README SHALL document two ways to reach a run — from a checkout, and from
the container image — each with what it needs in its environment and each with
a way to confirm it worked. The container path SHALL state what a packaged run
must be given from outside it, including the mount that gives the run a durable
history and what is lost without one.

The extension guide SHALL distinguish the two kinds of extension the project
accepts, because they have different shapes. Adding a notification channel is
implementing a port. Adding observability tooling is declaring specialists of
one's own — what a specialist declaration consists of, which parts are the
contributor's and which are supplied by the deployment, and that one working
specialist is a complete contribution rather than the first of a set that must
all be finished before anything runs.

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

#### Scenario: A run from the image

- **WHEN** an operator with a container runtime and no checkout follows the
  README's container instructions
- **THEN** they reach a complete run, having been told every setting it needs
  and where its history is kept

#### Scenario: A repeated local run keeps its history

- **WHEN** an operator follows the README's documented local invocation of the
  image a second time
- **THEN** the second run reads the history the first one recorded, without the
  operator restating where it is kept

#### Scenario: Adding a notification channel

- **WHEN** a contributor wants to plug in their own notification tooling
- **THEN** the extension guide tells them which port to implement, where the
  implementation belongs, and what tests it is expected to carry

#### Scenario: Adding observability tooling

- **WHEN** a contributor wants to investigate with their own observability
  platform
- **THEN** the extension guide tells them to declare a specialist — its tools,
  its instruction, its schema, and its signal — where that declaration belongs,
  and what tests it is expected to carry

#### Scenario: One specialist is a complete contribution

- **WHEN** a contributor declares a single specialist for a platform the
  project has never reached
- **THEN** the extension guide makes clear that it runs and contributes
  findings on its own, without any other specialist for that platform
  existing

#### Scenario: Dependencies are reproducible

- **WHEN** the project's dependencies are installed from the committed lockfile
- **THEN** the resolved versions are identical across machines and in CI
