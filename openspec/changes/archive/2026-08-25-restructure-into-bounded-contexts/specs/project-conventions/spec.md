## MODIFIED Requirements

### Requirement: Hexagonal import boundary is machine-enforced

The core domain and port definitions SHALL NOT depend on adapter code or on any
third-party integration library. The codebase SHALL be divided into bounded
contexts, each with its own inward-pointing layers, and a context SHALL NOT
reach into another context's internals: what one context offers another is a
published contract, and everything behind it is private. Any vocabulary shared
by more than one context SHALL depend on no context at all. Violations SHALL
fail an automated check, not rely on code review to catch them.

#### Scenario: Domain module imports an adapter

- **WHEN** a module in any context's domain layer imports from that context's
  adapters layer
- **THEN** the architecture check fails and names the offending module and the
  import that violated the boundary

#### Scenario: Port definition imports a vendor library

- **WHEN** a module in any context's ports layer imports a third-party
  integration library (for example a Datadog, agent-framework, or email client
  package)
- **THEN** the architecture check fails and names the offending module and import

#### Scenario: Adapter depends on domain and ports

- **WHEN** a module in a context's adapters layer imports from that context's
  domain or ports layers
- **THEN** the architecture check passes, because dependencies point inward

#### Scenario: A context reaches past another context's contract

- **WHEN** a module in one context imports from another context's domain or
  adapters
- **THEN** the architecture check fails and names the offending module and import

#### Scenario: A context uses another context's published contract

- **WHEN** a module in one context imports only the types another context
  publishes for that purpose
- **THEN** the architecture check passes, because that is the boundary the
  contract exists to be

#### Scenario: Two supporting contexts import each other

- **WHEN** a module in one supporting context imports from another supporting
  context
- **THEN** the architecture check fails, because neither is the other's
  supplier

#### Scenario: Shared vocabulary depends on a context

- **WHEN** a module holding vocabulary shared between contexts imports from any
  context
- **THEN** the architecture check fails, because shared vocabulary that depends
  on one context is that context's, not shared

#### Scenario: An enforced rule goes missing

- **WHEN** a rule this project is held to is no longer among those the
  architecture check runs
- **THEN** the check fails and names the missing rule, because a rule nobody
  runs is not a rule and a silently empty check reports success

#### Scenario: Compliant layout

- **WHEN** every module respects the inward dependency direction and every
  cross-context import goes through a published contract
- **THEN** the architecture check passes and reports no violations

## ADDED Requirements

### Requirement: A port is declared by the context that answers it

A port SHALL be declared in the context whose own adapter implements it, and
the failure a caller must distinguish SHALL be defined beside that port rather
than in the adapter that raises it or in the vocabulary the context publishes.
A context SHALL NOT declare a port that it neither implements nor calls.

#### Scenario: Locating what implements a port

- **WHEN** a contributor reads a port and wants to know what answers it
- **THEN** the implementation is an adapter of the same context, so the port
  and its implementations are found together

#### Scenario: A port's only caller is the composition root

- **WHEN** no module of any context calls through a port, and only the
  composition root does
- **THEN** the port still belongs to the context that answers it, because a
  composition root is entitled to name both ends and a context that sits on
  neither end of a port has no claim on it

#### Scenario: Catching the failure a port documents

- **WHEN** a caller needs to tell "this could not be done" from "this was done
  and there was nothing to report"
- **THEN** the failure type is reachable from the port itself, without reaching
  into the answering context's published vocabulary or its adapters

### Requirement: A module's tests are found where the module is

Test files SHALL be organised into the same package structure as the code they
cover, so that the tests for a module are located by the module's own path
rather than by searching for a name. Within that structure a test file SHALL be
named for the behaviour it establishes rather than for the module it exercises,
because a behaviour outlives the file that currently implements it.

#### Scenario: Locating the tests for a module

- **WHEN** a contributor wants the tests covering a given source module
- **THEN** they are in the test package that mirrors that module's package
  path, under each scope directory that tests it

#### Scenario: A module has no tests

- **WHEN** a source package has no corresponding test package
- **THEN** the absence is visible from the test tree's shape, rather than
  requiring the whole suite to be searched to establish it

#### Scenario: Scope is still decided by placement

- **WHEN** a test is added anywhere inside the mirrored structure
- **THEN** its scope marker is still derived from the top-level scope directory
  it lives under, not from its position within that directory and not from a
  hand-written marker

#### Scenario: A fixture is shared by one context's tests

- **WHEN** several tests of the same context need the same fixture
- **THEN** it is defined in the nearest shared configuration file within that
  context's test package, not in a helper module that tests import
