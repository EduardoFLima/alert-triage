## MODIFIED Requirements

### Requirement: Hexagonal import boundary is machine-enforced

The core domain and port definitions SHALL NOT depend on adapter code or on any
third-party integration library. The codebase SHALL be divided into bounded
contexts, each with its own inward-pointing layers, and a context SHALL NOT
reach into another context's internals: what one context offers another is a
published contract, and everything behind it is private. Any vocabulary shared
by more than one context SHALL depend on no context at all. Violations SHALL
fail an automated check, not rely on code review to catch them.

Within a context's adapters, a declaration SHALL NOT depend on the framework
machinery that runs it. The machinery depends on the declarations and never the
reverse: a declaration reaching into the machinery — for a constant, a type, or
anything else — is what makes it framework-specific, in a tree whose point is
that a declaration outlives the framework currently running it. This SHALL fail
the same automated check.

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

#### Scenario: A declaration imports the framework that runs it

- **WHEN** a module declaring an agent imports from the framework machinery
  that turns declarations into running agents
- **THEN** the architecture check fails and names the offending module and
  import

#### Scenario: The framework machinery imports a declaration

- **WHEN** a module of the framework machinery imports a declaration in order
  to run it
- **THEN** the architecture check passes, because that is the direction the
  dependency is meant to point

#### Scenario: An enforced rule goes missing

- **WHEN** a rule this project is held to is no longer among those the
  architecture check runs
- **THEN** the check fails and names the missing rule, because a rule nobody
  runs is not a rule and a silently empty check reports success

#### Scenario: Compliant layout

- **WHEN** every module respects the inward dependency direction and every
  cross-context import goes through a published contract
- **THEN** the architecture check passes and reports no violations
