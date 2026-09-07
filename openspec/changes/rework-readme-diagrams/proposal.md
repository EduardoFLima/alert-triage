## Why

Capability slice 15 in [`docs/vision.md`](../../../docs/vision.md#capability-slices-dependency-order).
The diagram the bounded-context restructure left behind states the shape
correctly and reads poorly — four nested subgraphs, an enclosing box for
configuration, and a rung per layer inside each context, all competing for the
same glance. It also answers a question most readers do not arrive with: it
says what the contexts are and how they depend on each other, while a reader
opening the README first wants to know what happens to one alert on its way to
a report. Every slice that would change what the picture has to say has
landed, so redrawing now is redrawing once.

## What Changes

- **Two pictures, not one.** A *journey of an alert* flow in the introduction,
  answering what a run does; and a simplified *bounded contexts* map in
  Architecture, answering how the code is arranged. Each stays short — the
  detail belongs in the prose and the tree already beside them.
- The existing Architecture mermaid diagram is **replaced**, not amended: no
  nested per-context subgraphs, no enclosing configuration box, no rung per
  layer.
- Both are generated through the mermaid MCP tool, per the repo convention in
  [`AGENTS.md`](../../../AGENTS.md).
- **`Setup` and `Running it` become one section.** `## Getting started`, with
  `### Setup` and `### Running it` beneath it — they are two halves of one
  question a newcomer asks once, and splitting them at the top level is part
  of why the settings ended up described twice. `In a container` stays inside
  `Running it`, one level deeper, because it is a way to reach a run rather
  than a third thing to do.
- **Each setting is described once, in the reference.** Two passages of
  `Configure` are already in
  [`docs/configuration.md`](../../../docs/configuration.md) and stated better
  there — the rule deciding whether a setting is behaviour or connection, and
  the note that a `.env` only supplements the environment. Those are
  **deleted, not moved**. The third, the two `cp` lines that copy the annotated
  examples, is **moved**: the reference names those files but gives nothing to
  run, and the block's trailing comments say in four words each which file is
  safe to commit and which must never be. What stays is the minimum a first run
  needs, a one-line mention of the example files, and the behaviour/connection
  split as a two-item list rather than a paragraph.
  `Running it`'s environment rundown goes the same way: it keeps saying *what
  a run needs*, because the spec requires it, and stops being a second account
  of how each variable behaves.
- **Two documentation conventions**, in [`AGENTS.md`](../../../AGENTS.md)
  beside the existing one about diagrams:
  - *What is enumerated is written as a list.* Where documentation names
    several of a thing, it sets them out as a list rather than as an extended
    paragraph, so the count is carried by the shape of the page instead of by
    bold text mid-sentence.
  - *Documentation does not restate what a document it links already says.*
    `AGENTS.md` already carries the converse — that it must never duplicate
    the README — so this completes a rule the repo half-states rather than
    inventing one. It is what the `Configure` and `Development` cuts below are
    instances of.
- **`In a container` shrinks to its command, and the rest moves to
  `docs/containerized.md`.** Ninety-odd lines — a five-row flag table, bind-
  mount ownership, `compose.yaml` and its override file — sit on the front
  page for a path most readers are not on. The README keeps the build and run
  commands, the fact that the image *is* the run, one sentence on the durable
  mount, and a link. Everything else moves.
- **`Development` loses two explanations it does not owe the reader.** The
  account of why the image is not a fifth command, and the note on where scope
  markers come from, are both already in `AGENTS.md`, which the section
  already links. The commands stay; the explaining goes.
- **`Extending it` is rewritten to it.** The two kinds of extension become two
  bullets, and the pointer to [`docs/adapters.md`](../../../docs/adapters.md)
  leaves the paragraph for a line of its own, because it belongs to both kinds
  rather than to whichever one it currently trails. The convention is applied
  to the rest of `README.md` in the same pass — `Setup → Configure`'s
  behaviour/connection pair and `Architecture`'s four contexts have the same
  shape.

Out of scope: a deployment diagram (the container section's prose and flag
table already carry the image, the mount and what is handed in from outside);
applying the new convention beyond `README.md`, since `docs/` is a sweep of its
own and this change is the README's; anything about the code itself. This
change touches documentation only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-conventions`: the requirement that contributors can set up and
  verify the project from the README changes in three ways. It gains what the
  README's diagrams must each answer — one for what a run does, one for how
  the contexts depend on each other. It requires the settings reference to be
  stated in one place rather than restated per section. And it lets the
  container path's detail live in a document the README links, on the same
  terms it already grants the extension guide, while requiring the durable-
  mount warning to stay on the page itself — a link is not a warning, and that
  failure is silent.

## Impact

- `README.md` — the introduction, the merged `Getting started` (which absorbs
  `Setup` and `Running it`), `Development`, `Architecture`, and
  `Extending it`. The
  `#in-a-container` anchor survives, since GitHub derives it from the heading
  text and only its level changes; `docs/configuration.md` links to it.
- `AGENTS.md` — one added convention about how documentation sets out what it
  enumerates. Reached through `CLAUDE.md` and `GEMINI.md` unchanged, since both
  are symlinks to it.
- `docs/containerized.md` — **new**. Receives the flag table, the bind-mount
  ownership rules, and the `compose.yaml` and override-file guidance that
  `In a container` currently carries. `docs/configuration.md` already links
  the README's container section by anchor, so that link is re-pointed.
- `docs/configuration.md` — gains the two `cp` lines, beneath the paragraph
  that already names the example files, and has its `#in-a-container` link
  re-pointed at the new document. Otherwise unchanged: it is the destination of
  the settings pointer and already carries what else the README stops saying.
- `openspec/specs/project-conventions/spec.md` — via the delta. The new
  convention adds no requirement of its own: the spec enforces that agent
  instructions have one source of truth, not what practices that file
  mandates, exactly as it already leaves TDD and clean code to `AGENTS.md`.
- No source, test, or dependency changes. The four gate commands are unaffected;
  acceptance is a reader reaching the right mental model unaided, which is a
  judgement rather than a test and does not gate a green build.
