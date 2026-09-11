## Context

See `proposal.md` — Why. The constraint that shapes everything below is that
`README.md` is the only place these pictures live and GitHub renders it
directly, so a diagram is a fenced `mermaid` block rather than a file or an
image. The requirement being changed is in
`specs/project-conventions/spec.md`.

## Goals / Non-Goals

**Goals:**

- Each picture answers exactly one question, and is legible without zooming.
- The flow picture is checkable against the code rather than drawn from
  memory.

**Non-Goals:**

- Redrawing a context's internal layering. The inward rule is one sentence of
  prose and is enforced by `tests/unit/test_architecture.py`; drawing it four
  more times is what made the current picture busy.
- Moving either diagram out of `README.md`. Both stay on the front page; the
  only new document is `docs/containerized.md`, which carries prose rather than
  a picture.
- Applying the new list convention outside `README.md`. `docs/` is a sweep of
  its own, and folding it in here would bury the diagram rework it is named
  for.

## Decisions

**Two pictures rather than one or three.** A single diagram has to answer both
"what does this do" and "how is the code arranged" and reads as a compromise
between them — which is the current state. A third, for deployment, was
considered and dropped: the container section already carries the image, the
mount and what is handed in from outside in prose plus a per-flag table, and a
picture there would restate that rather than clarify it.

**The flow picture goes in the introduction, above the first heading.** The
alternative was `Running it`, beside the invocation it describes. But a reader
deciding whether this project is for them stops before `Getting started`, and
never reaches the invocation; the question the flow answers is asked in the
first thirty seconds or not at all.

**The flow is drawn from the run's own stages.** `app/pipeline.py` already
names them — fetch, read the ledger, investigate, deliver, record — for the
purpose of saying which one failed. Drawing those rather than an invented
sequence gives the picture a source of truth in the code and one obvious place
to check it against when the pipeline changes.

**The context picture is flat: one node per context, edges labelled with what
crosses them.** No nested subgraphs, no enclosing box for configuration, no
rung per layer. `triage` reaches `investigation` and `notification` through
their contracts, and `app` composes. The enclosing box was doing the work of a
sentence, and cost the diagram its shape to do it.

`configuration` and `shared` are then left out of the picture altogether rather
than drawn beneath it, which is a decision taken while drawing. Both are
depended on by every context, so an honest drawing is six dotted edges — six
lines to carry one sentence, which is the enclosing box's mistake in a
different notation. They keep their sentence in the prose and their entry in
the source tree directly below, where the description each needs is a phrase
rather than a shape.

**Both are generated through the mermaid MCP tool**, per `AGENTS.md`, rather
than hand-written — the same convention the existing diagram was produced
under.

**What is enumerated is written as a list, and that is a convention rather than
a one-off.** `Extending it` names two kinds of extension and sets them in a
single paragraph, so the count is carried by bold text mid-sentence and a
reader has to parse the prose to find out there are two — the same complaint as
the diagram, one section down. Fixing only that section would leave the same
shape in `Setup → Configure` and in `Architecture`, so the rule goes in
`AGENTS.md` beside the existing one about diagrams and the README is brought to
it in one pass. It lands in `AGENTS.md` rather than in the spec because the
spec enforces that agent instructions have a single source of truth and does
not enumerate the practices that file mandates — TDD and clean code live there
on the same terms. The alternative, a spec requirement, was rejected for
specifying layout: a list and a paragraph carry the same information, and
OpenSpec's own test is whether the result can change without changing
observable behaviour.

**`Setup` and `Running it` merge, and the merge is what makes the
deduplication obvious.** They are two halves of one question — a newcomer asks
"how do I get this running" once, not twice — and having them as peers at the
top level is a good part of why the settings came to be described in both. Once
they are subsections of one `Getting started`, a second account of the same
variables a screen apart reads as the duplication it is. `In a container`
becomes a fourth-level heading inside `Running it` rather than a third
subsection, because it is a *way to reach a run* and not a third thing to do
after setting up and running; the alternative, flattening all three into peers,
would have put the checkout path and the image path at different depths from
the section that introduces them. Its heading text does not change, so the
`#in-a-container` anchor `docs/configuration.md` links to still resolves.

**The deduplication removes explanation, not information.** `Running it` keeps
naming what a run needs, because the spec requires each path to a run to state
that. What it stops doing is re-teaching each variable's behaviour and default
alongside the name, which `Configure` introduces and `docs/configuration.md`
defines properly. Nothing is deleted that only the README said.

**That check has been run for `Configure`, and it deletes twice and moves
once.** Two of its passages are already in `docs/configuration.md`, and in each
case the reference states it better, so the README copy is not merely redundant
but the weaker of the two:

- The behaviour/connection rule — `docs/configuration.md` lines 10–18, which
  also give the test for deciding where a *new* setting goes.
- That a `.env` only supplements the environment — lines 118–122, under "The
  process wins", with the container, systemd and CI reasoning the README's
  one-sentence version drops.

The third is a move, and the distinction matters. Lines 5–8 of the reference
*name* both example files and say to copy them rather than starting blank, but
they carry no runnable command. The README's two `cp` lines do, and their
trailing comments state in four words each what the reference spends a
paragraph on — which file is behaviour and safe to commit, which is connection
and must never be. So the block goes into `docs/configuration.md` directly
beneath the paragraph that already names those files, where a reader has just
been told they exist and has nothing to run.

So `Configure` keeps the minimum a first run needs, mentions the example files
in one line, states the behaviour/connection split as a two-item list under the
new convention, and points at the reference for the rest. The line numbers are
where they were when this was written; confirm the content is still there
before deleting, rather than trusting the numbers.

**`Development` is the same finding again, which is what makes it a convention
rather than three cuts.** Its account of why the image is not a fifth command
is `AGENTS.md` lines 131–135, and its note on where scope markers come from is
lines 28–29 — and the section already ends by linking `AGENTS.md`. Having now
found the same thing in `Configure`, in `Running it` and here, the durable fix
is a rule rather than three deletions: *documentation does not restate what a
document it links already says.* The repo half-states it already, from the
other end — `AGENTS.md` must never duplicate the README — so this completes a
rule rather than introducing one, which is also why it belongs beside that
statement rather than in the spec.

**The container detail moves out, but the warning does not.** `In a container`
is the longest section in the README and serves the smaller audience, so the
flag table, the bind-mount ownership rules and the `compose.yaml` guidance go
to `docs/containerized.md`. What cannot go with them is the durable mount: a
run without it keeps no history and still exits `0`, which is precisely the
failure slice 14 existed to make avoidable, and a reader who never clicks the
link would meet it in production. So the README keeps the run command, one
sentence naming the mount and what is lost without it, and the link — and the
spec is changed to permit exactly that split rather than being quietly
outgrown. The allowance is not new: the same requirement already lets the
extension guide live in a linked document, for the same reason, so the
container path is being brought under a rule the requirement already contains.

The risk in the rule is the opposite of the one it fixes: a README that points
everywhere and says nothing is worse than one that repeats itself. So the rule
is about *explanation*, not about facts. A section still names what it needs
and gives the commands to run; what moves to the linked document is the
reasoning about why. `Development` keeps all four commands and every pytest
selection, and loses only the two paragraphs explaining them.

## What changed during implementation

The architecture pictures did not ship as designed above. After a mermaid
version and a hand-drawn ASCII one, the maintainer drew them in draw.io, and
three decisions above were superseded:

- **Not both mermaid.** The run flow in the introduction is mermaid. The
  architecture is five editable SVGs in `docs/diagrams/` — an overview in the
  README and one deep dive per context — each carrying its own source, so the
  convention in `AGENTS.md` and `docs/vision.md` was amended to allow them.
- **Configuration is drawn.** The overview shows it as a peer every context
  reads, with explicit arrows. That turned out legible, which the reasoning
  above did not expect of a picture rather than a sentence.
- **A second new document.** The four deep dives live in
  `docs/architecture.md`, a level below the README, rather than on the front
  page.

The spec delta holds as written: the README still carries two diagrams
answering two questions, and neither redraws a context's internal layering —
the deep dives that do are in the linked document.

## Risks / Trade-offs

- **A diagram that renders in a previewer but not on GitHub.** → Stay within
  the plain `flowchart` syntax and `classDef` styling the current README
  already proves renders there; render the result before committing.
- **The dedup drops something `docs/configuration.md` does not carry.** →
  Diff the two lists before removing, and move anything unique rather than
  deleting it.
- **The list convention, taken literally, shreds prose into fragments.** Not
  every sentence that mentions two things is an enumeration, and a page of
  one-line bullets reads worse than the paragraph it replaced. → State the
  convention as being about what a passage *enumerates* — a set a reader is
  meant to hold — rather than about any sentence containing more than one
  noun, and apply it in this pass only where the paragraph is already doing a
  list's job.
- **Acceptance is a judgement, not a test.** A reader reaching the right mental
  model unaided cannot be asserted, so this change does not gate a green build.
  → The spec's scenarios are the part that is checkable; the rest is a human
  read of the rendered page, which the task list makes an explicit step rather
  than an assumption.
