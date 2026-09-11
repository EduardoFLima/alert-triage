## ADDED Requirements

### Requirement: Every circuit breaker key is read by what it bounds
Every key the `circuit_breakers` section resolves SHALL be read by the thing it
names. A key that nothing enforces SHALL be removed from the schema rather than
resolved and ignored, so that an operator setting a breaker is always changing
behavior. This is the same rule that makes an unknown section a refusal: a value
that resolves nothing is almost always a value an operator believes is
resolving something.

The section SHALL resolve exactly these keys, each read by what it bounds:

- `max_agent_hops` — how many specialist consultations one investigation may
  make, defaulting to eight.
- `max_tool_calls_per_agent` — how many tool calls one specialist may make
  within one investigation, defaulting to twelve.
- `max_investigation_duration_seconds` — how long one investigation may run,
  defaulting to three hundred.
- `mcp_call_timeout_seconds` — how long one call to an observability platform
  may take, defaulting to thirty.

Each SHALL be resolved independently of the others and of every other section:
they bound different things and will be tuned against different evidence.

#### Scenario: A breaker an operator sets changes behavior
- **WHEN** a deployment sets any key in the `circuit_breakers` section
- **THEN** the value reaches what that key bounds, rather than being resolved
  and left unread

#### Scenario: Breakers are resolved independently of each other
- **WHEN** an operator changes one breaker
- **THEN** every other breaker resolves to what it was, defaults included

#### Scenario: The section is still optional
- **WHEN** `config.yaml` declares no `circuit_breakers` section
- **THEN** every breaker resolves to its documented default and bounds what it
  names, rather than bounding nothing

### Requirement: A hop is a specialist consultation
`max_agent_hops` SHALL mean how many times one investigation's reasoning may
reach out to a specialist, and SHALL default to eight. Its default SHALL exceed
the number of specialists a deployment declares, so that an unconfigured
deployment can consult every signal and still ask a follow-up.

It SHALL NOT mean a depth limit on agents calling agents. No declaration can
express an agent beneath a specialist, so a bound on that depth would be a
setting an operator could not reach and a rule nothing could violate.

#### Scenario: The documented default admits the whole crew
- **WHEN** a deployment configures no hop bound
- **THEN** the resolved bound is eight, which exceeds the number of specialists
  declared

#### Scenario: The hop bound is what the investigation is held to
- **WHEN** a deployment sets `max_agent_hops`
- **THEN** that is the number of specialist consultations the investigation may
  make

### Requirement: A breaker key that nothing can enforce is refused by name
`max_mcp_retries` SHALL NOT be a key of the `circuit_breakers` section. How many
times a call to an observability platform is retried is owned by the agent
framework's own client, and there is no seam through which an operator's value
could reach it.

A deployment that still sets it SHALL be refused at startup with the key named,
by the same path that refuses any key the schema does not resolve — not started
with the setting silently unread.

#### Scenario: A deployment still setting the retired key is refused
- **WHEN** `config.yaml` declares `circuit_breakers.max_mcp_retries`
- **THEN** the system refuses to start and names that key

#### Scenario: The retired key has no environment override either
- **WHEN** `MAX_MCP_RETRIES` or `CIRCUIT_BREAKERS_MAX_MCP_RETRIES` is set in
  the environment
- **THEN** nothing resolves from it and no retry behavior changes

### Requirement: The platform call timeout is what bounds a platform call
`mcp_call_timeout_seconds` SHALL bound how long one call to an observability
platform may take, both while the connection is being established and while its
response is being read. The configured value SHALL be the one in force, so that
the agent framework's own defaults cannot apply to a bound this deployment has
stated.

It SHALL be resolved independently of ingestion's `request_timeout_seconds`:
one bounds an agent's calls during investigation and the other bounds a fetch of
alerts, and equal defaults are not a shared concept.

#### Scenario: The configured timeout is the one in force
- **WHEN** a deployment sets `mcp_call_timeout_seconds`
- **THEN** a platform call is bounded by that value rather than by the
  framework's default

#### Scenario: An unset timeout is the documented default, not the framework's
- **WHEN** a deployment sets no `mcp_call_timeout_seconds`
- **THEN** a platform call is bounded by the documented default of thirty
  seconds rather than by whatever the framework would otherwise apply

#### Scenario: Ingestion's timeout is untouched
- **WHEN** an operator changes `mcp_call_timeout_seconds`
- **THEN** ingestion's `request_timeout_seconds` is unchanged, and the reverse
