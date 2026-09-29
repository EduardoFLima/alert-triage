## ADDED Requirements

### Requirement: Scope names the environment a run watches
`scope` SHALL carry an `env` key naming the one environment whose alerts a run
watches, resolvable from `config.yaml`, from `SCOPE_ENV`, or both, with the
environment winning where both are set. Where neither sets it, `env` SHALL
resolve to `prod`.

`env` SHALL narrow the owner and services filters and SHALL NOT satisfy
`scope` on its own: a deployment that resolves an environment and neither an
owner nor services SHALL still refuse to start, so that the default never
turns into "watch everything in production".

`env` SHALL be a single value. It SHALL be named in platform-neutral terms, as
the other scope keys are; translating it into a platform's own vocabulary is
the alert source adapter's responsibility.

An empty `env` SHALL be refused rather than read as "any environment", so that
clearing the value can never silently widen a run.

#### Scenario: Environment defaults to production
- **WHEN** neither `config.yaml` nor the environment sets `scope.env`
- **THEN** the resolved scope watches the `prod` environment

#### Scenario: Environment set in the file
- **WHEN** `config.yaml` sets `scope.env` to `staging` and `SCOPE_ENV` is unset
- **THEN** the resolved scope watches `staging`

#### Scenario: The environment variable wins
- **WHEN** `config.yaml` sets `scope.env` to `staging` and `SCOPE_ENV` is `prod`
- **THEN** the resolved scope watches `prod`

#### Scenario: Environment alone does not satisfy scope
- **WHEN** `scope.env` resolves and neither `scope.owner` nor `scope.services`
  does
- **THEN** the system refuses to start and reports that `scope` requires an
  owner, services, or both

#### Scenario: An empty environment is refused
- **WHEN** `scope.env` or `SCOPE_ENV` is set to an empty or blank value
- **THEN** the system refuses to start and names the key
