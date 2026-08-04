## Purpose

Defines the repo's self-enforcing engineering rules: the hexagonal import
boundary that keeps the core domain independent of any observability,
agent-framework, or notification vendor, and the automated quality gate every
change passes before merge. These rules exist so the architecture described in
`docs/vision.md` survives contact with a growing codebase and with outside
contributors adding their own adapters.

## Requirements

### Requirement: Hexagonal import boundary is machine-enforced

The core domain and port definitions SHALL NOT depend on adapter code or on any
third-party integration library. Violations SHALL fail an automated check, not
rely on code review to catch them.

#### Scenario: Domain module imports an adapter

- **WHEN** a module in the domain layer imports from the adapters layer
- **THEN** the architecture check fails and names the offending module and the
  import that violated the boundary

#### Scenario: Port definition imports a vendor library

- **WHEN** a module in the ports layer imports a third-party integration library
  (for example a Datadog, agent-framework, or email client package)
- **THEN** the architecture check fails and names the offending module and import

#### Scenario: Adapter depends on domain and ports

- **WHEN** a module in the adapters layer imports from the domain or ports layers
- **THEN** the architecture check passes, because dependencies point inward

#### Scenario: Compliant layout

- **WHEN** every module respects the inward dependency direction
- **THEN** the architecture check passes and reports no violations

### Requirement: Agent instructions have a single source of truth

The repository SHALL expose exactly one authored file of agent instructions.
Harness-specific instruction filenames SHALL resolve to that same file rather
than duplicating its content, and the file SHALL describe engineering practices
without restating what the application does.

#### Scenario: Reading via a harness-specific filename

- **WHEN** a coding agent reads a harness-specific instruction file such as
  `CLAUDE.md` or `GEMINI.md`
- **THEN** it receives the byte-identical content of the canonical `AGENTS.md`

#### Scenario: Instructions are edited

- **WHEN** the canonical instruction file is edited
- **THEN** every harness-specific filename reflects the edit with no further
  action, because none of them holds an independent copy

#### Scenario: Product knowledge is requested

- **WHEN** a contributor or agent needs to know what the application does
- **THEN** that information is found in the README, and the agent instruction
  file does not duplicate it

### Requirement: Quality gate runs on every change

Lint, formatting, static type checking, and the full test suite SHALL run
automatically on pushes and pull requests. A failure in any of them SHALL fail
the overall check.

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

#### Scenario: Change passes every check

- **WHEN** a pull request passes lint, formatting, type checking, and all tests
- **THEN** the gate reports success

### Requirement: Contributors can set up and verify the project from the README

The README SHALL give a contributor an unfamiliar-machine path to a working
environment and a way to confirm the setup succeeded, and SHALL carry the
architecture diagram and the extension guide for adding new adapters.

#### Scenario: Fresh clone

- **WHEN** a contributor clones the repository and follows the README setup steps
  on a machine with no prior project state
- **THEN** they reach an environment where the documented verification command
  runs the test suite successfully

#### Scenario: Adding an adapter

- **WHEN** a contributor wants to plug in their own observability or notification
  tooling
- **THEN** the README tells them which port to implement, where the
  implementation belongs, and what tests it is expected to carry

#### Scenario: Dependencies are reproducible

- **WHEN** the project's dependencies are installed from the committed lockfile
- **THEN** the resolved versions are identical across machines and in CI

### Requirement: Test suite separates fast and integration-scope tests

The test harness SHALL distinguish tests that run with no external dependency
from those that exercise integrations, so the fast set can be run on its own
during development.

#### Scenario: Running the fast set

- **WHEN** a developer runs the unit-scope test selection
- **THEN** only tests requiring no external service execute, and they execute
  without network access

#### Scenario: Running everything

- **WHEN** the full suite is run
- **THEN** both unit-scope and integration-scope tests execute and coverage is
  reported
