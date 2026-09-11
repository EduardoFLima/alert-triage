## MODIFIED Requirements

### Requirement: Contributors can set up and verify the project from the README

The README SHALL give a contributor an unfamiliar-machine path to a working
environment and a way to confirm the setup succeeded, and SHALL carry the
extension guide for adding new adapters.

The README SHALL carry two diagrams, because a reader arrives with one of two
different questions and a single picture answers them badly. One SHALL show
what a run does to an alert on its way to a delivered report, and SHALL appear
before the reader is asked to install or configure anything. The other SHALL
show the bounded contexts and how they depend on one another, and SHALL appear
with the architecture prose it illustrates. Each SHALL be readable at a glance:
neither is the place for a context's internal layering, which the prose and the
source tree beside it already give.

The README SHALL document two ways to reach a run — from a checkout, and from
the container image — each with what it needs in its environment and each with
a way to confirm it worked.

For the container path the README SHALL carry the command that performs a run
and SHALL state, on the page itself, the mount that gives the run a durable
history and what is lost without one — because a run missing it keeps nothing
and still succeeds, so a reader who never follows the link must still be
warned. What a packaged run must otherwise be given from outside it — the
individual flags, the filesystem ownership a bind mount requires, and any
convenience for repeating a run — MAY live in a document the README links,
on the same terms as the extension guide below.

Each setting SHALL be explained in one place. The README SHALL state what a run
needs and point to the settings reference, and SHALL NOT restate how an
individual setting behaves in more than one of its sections.

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

#### Scenario: A run from the image

- **WHEN** an operator with a container runtime and no checkout follows the
  README's container instructions
- **THEN** they reach a complete run, having been told every setting it needs
  and where its history is kept

#### Scenario: A repeated local run keeps its history

- **WHEN** an operator follows the documented local invocation of the image a
  second time, whether the README carries it or the document the README links
- **THEN** the second run reads the history the first one recorded, without the
  operator restating where it is kept

#### Scenario: A reader who never follows the container link

- **WHEN** an operator runs the image from the README alone, without opening
  the document it links for the detail
- **THEN** they have been told that the run needs a durable mount and that
  without one it keeps no history while still exiting successfully, because
  that failure is silent and a link is not a warning

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


#### Scenario: A reader wants to know what the thing does

- **WHEN** someone opens the README having never seen the project
- **THEN** a diagram in its introduction shows what one alert passes through on
  its way to a delivered report, before any instruction to install or configure
  anything

#### Scenario: A reader wants to know how the code is arranged

- **WHEN** a contributor reads the architecture section
- **THEN** a diagram shows the bounded contexts and the direction of the
  dependencies between them, without redrawing the layers inside any of them

#### Scenario: Looking up how a setting behaves

- **WHEN** a reader wants to know what a given setting does or what it defaults
  to
- **THEN** the README names what a run needs and sends them to one reference,
  rather than describing that setting a second time in another section
