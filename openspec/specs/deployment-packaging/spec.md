# deployment-packaging Specification

## Purpose

Defines the distributable artefact a run ships as: a container image that
performs one complete triage run on any machine with a container runtime,
carrying the dependency set the gate verified, holding no deployment's secrets,
and keeping the run's history outside itself so a packaged run is continuous
with the one before it.

## Requirements

### Requirement: The image performs one complete run unargued

The image SHALL perform, when started with no arguments, the same complete run
the installed command performs, and SHALL then exit. Its exit status SHALL carry
the run's outcome under the same meanings an uncontainerized run uses, so that
whatever starts the container reads success and failure without knowing it is a
container.

#### Scenario: Started with no arguments

- **WHEN** the image is started with no command and no arguments
- **THEN** it performs one complete run — fetch, group, decide, report, record —
  and the process exits rather than looping or waiting

#### Scenario: A successful run

- **WHEN** a packaged run decides, reports and records everything it fetched
- **THEN** the container exits `0`

#### Scenario: A run that could not proceed

- **WHEN** a packaged run is given configuration it refuses to start on
- **THEN** the container exits non-zero and its output names what is missing,
  rather than exiting `0` having done nothing

### Requirement: The image carries the verified dependency set

The image SHALL install its dependencies from the committed lockfile, so the
versions it runs on are the versions the quality gate resolved and tested. It
SHALL NOT carry development-only tooling, and SHALL NOT resolve dependencies
afresh at build time from anything but that lockfile.

#### Scenario: Versions match what was verified

- **WHEN** the image is built
- **THEN** the runtime dependency versions inside it are those pinned in the
  committed lockfile

#### Scenario: A stale lockfile fails the build

- **WHEN** the lockfile does not agree with the declared dependencies
- **THEN** the build fails rather than silently resolving a different set

#### Scenario: Development tooling is absent

- **WHEN** the built image is inspected
- **THEN** the test, lint, and type-checking tooling used to develop the project
  is not installed in it

### Requirement: A packaged run is unprivileged

The image SHALL run the job as a non-root user, and the run SHALL need no
elevated privilege to do anything it does.

#### Scenario: The run's user

- **WHEN** a packaged run executes
- **THEN** the process is owned by a non-root user

#### Scenario: The mounted state is writable by that user

- **WHEN** a durable volume is mounted at the location the image keeps the
  ledger
- **THEN** the run's own user can create and write the ledger there

### Requirement: The history a run keeps outlives the container

A container's own filesystem does not survive the run, and an incident history
that does not survive is one that silently disables deduplication, continuation,
and the re-notify cooldown while the run still reports success. The image SHALL
therefore keep the ledger at a fixed, documented location intended to be
mounted from outside, and consecutive packaged runs sharing that mounted
location SHALL be continuous with one another. Documentation SHALL state that a
run given no durable mount keeps no history between runs.

#### Scenario: The ledger is created on the mount, not inside the container

- **WHEN** a packaged run is given a durable mount at the location the image
  keeps the ledger
- **THEN** the ledger is present and readable on that mount after the container
  is gone

#### Scenario: A second run keeps what the first one left

- **WHEN** a second run executes in a separate container over the same mounted
  location, holding an incident the first one recorded
- **THEN** that incident is still on record afterwards, having been opened
  rather than replaced by an empty ledger

#### Scenario: The location is documented

- **WHEN** an operator reads the documented way to run the image
- **THEN** it shows the mount that gives the run a durable history, and says
  what is lost without it

### Requirement: A packaged run is configured from outside the image

The image SHALL contain no deployment's credentials and no deployment's
behavior configuration. Every setting a run needs SHALL be suppliable to the
container from outside it, and the image SHALL be usable by a second deployment
with different settings without being rebuilt.

#### Scenario: The image carries no credential

- **WHEN** the built image is inspected
- **THEN** it contains no credential, no environment file holding one, and no
  deployment's behavior configuration file

#### Scenario: Settings supplied to the container

- **WHEN** a run's mandatory settings are supplied to the container as
  environment variables
- **THEN** the run resolves them and proceeds, needing no file placed beside it

#### Scenario: One image, two deployments

- **WHEN** the same image is started twice with different settings
- **THEN** each run behaves according to the settings it was given, with no
  rebuild between them

### Requirement: The build context excludes run state and secrets

The build SHALL exclude local environment files, the local ledger and its
directory, virtual environments, and caches, so that a build performed in a
working checkout cannot copy a developer's credentials or run history into the
image.

#### Scenario: A build from a working checkout

- **WHEN** the image is built in a checkout containing a local environment file
  and a local ledger
- **THEN** neither is present in the resulting image

### Requirement: The image is built and exercised by the quality gate

The image build SHALL run automatically on every change, and a Dockerfile that
no longer builds SHALL fail the gate. The packaged run SHALL be exercised
against a built image by tests that need no credentials, and those tests SHALL
skip — announcing why — where no container runtime is available, so that a
checkout without one still runs green.

#### Scenario: The Dockerfile stops building

- **WHEN** a change breaks the image build
- **THEN** the gate reports failure, rather than passing on a suite that never
  built it

#### Scenario: A misconfigured packaged run is refused

- **WHEN** the gate starts the built image with the mandatory scope absent
- **THEN** the run refuses to start, names the missing setting, and the
  container exits non-zero

#### Scenario: A fully configured packaged run reaches the platform

- **WHEN** the gate starts the built image with every setting supplied and a
  durable mount, and the platform it is pointed at cannot be reached
- **THEN** the run gets through building everything it needs — every dependency
  present, every adapter constructible, the ledger created on the mount — and
  fails naming the fetch, rather than failing on anything the image itself got
  wrong

#### Scenario: No container runtime available

- **WHEN** the suite runs on a machine with no container runtime
- **THEN** the container tests skip and report that as the reason, and the rest
  of the suite passes
