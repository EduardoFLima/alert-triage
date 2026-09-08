## 1. The journey of an alert

- [x] 1.1 Read `src/alert_triage/app/pipeline.py` and write down the stages a
      run actually passes through, so the picture is drawn from the code rather
      than from the prose about it
- [x] 1.2 Draft the flow through the mermaid MCP tool: alert in, report out,
      the ledger's decision visible as the reason a run may report nothing
- [x] 1.3 Place it in the introduction, above the first heading, with at most a
      sentence of lead-in — the prose beneath it already says what it does
- [x] 1.4 Render and confirm it is legible at GitHub's width without zooming

## 2. The bounded contexts

- [x] 2.1 Draft the replacement through the mermaid MCP tool: one node per
      context, `asks` and `publishes` on the two contract edges, `app`
      composing, `configuration` and `shared` beneath — no nested subgraphs, no
      enclosing box, no rung per layer
- [x] 2.2 Replace the existing diagram in `## Architecture` outright, keeping
      the surrounding prose, the source tree, and the note that both rules are
      enforced by `tests/unit/test_architecture.py`
- [x] 2.3 Check the prose still reads correctly now that configuration is no
      longer drawn around the other contexts — the sentence explaining why the
      diagram encloses it no longer describes the picture
- [x] 2.4 Render and confirm it is legible at GitHub's width without zooming

## 3. One section for getting it running, saying each setting once

- [x] 3.1 Merge `## Setup` and `## Running it` into a single
      `## Getting started` with two subsections, `### Setup` and
      `### Running it`, keeping the prose of each intact for now
- [x] 3.2 Demote `In a container` to `#### In a container` inside
      `### Running it`, leaving its heading text alone — the level changes but
      the `#in-a-container` anchor does not, since GitHub derives it from the
      text
- [x] 3.3 Move the two `cp` lines that copy `config.example.yaml` and
      `.env.example` into `docs/configuration.md`, directly beneath the
      paragraph that already names those files, keeping their trailing
      comments — the reference names the files but gives nothing to run
- [x] 3.4 Confirm the other two passages named in `design.md` are still in
      `docs/configuration.md`, then delete them from `Configure`: the
      behaviour/connection rule, and the note that a `.env` only supplements
      the environment
- [x] 3.5 Leave `Configure` holding the minimum a first run needs, a one-line
      mention that `config.example.yaml` and `.env.example` exist, the
      behaviour/connection split as a two-item list, and the pointer to the
      reference — nothing that teaches an individual setting
- [x] 3.6 Diff the `Running it` environment list against
      `docs/configuration.md`; move anything only the README carries into that
      reference before removing it
- [x] 3.7 Reduce that list to what a run needs plus a pointer to the reference
- [x] 3.8 Re-read the merged section end to end: with the two halves adjacent,
      cut whatever else now says the same thing twice
- [x] 3.9 Confirm the container subsection is still reachable as the second
      path to a run the spec requires; what it must still say on the page
      itself is settled by group 5

## 4. Two conventions, and the README brought to them

- [x] 4.1 Add the list convention to `AGENTS.md` under `Looking things up`,
      beside the existing rule about diagrams: where documentation names
      several of a thing, set them out as a list rather than as an extended
      paragraph. Word it about what a passage enumerates, not about any
      sentence holding more than one noun
- [x] 4.2 Add the second convention beside it: documentation does not restate
      what a document it links already says. Word it about explanation rather
      than about facts — a section still names what it needs and gives the
      commands to run
- [x] 4.3 Confirm `CLAUDE.md` and `GEMINI.md` still resolve to the edited file
      — they are symlinks, so this should need no action, which is the point
- [x] 4.4 Rewrite `Extending it`: the two kinds of extension become two
      bullets, and the pointer to `docs/adapters.md` moves to a line of its
      own, since it belongs to both kinds rather than trailing the second
- [x] 4.5 Apply the list convention to the other place in `README.md` whose
      paragraph is already doing a list's job — `Architecture`'s four
      contexts. `Configure`'s behaviour/connection pair is the same shape and
      is dealt with by task 3.5, not twice here
- [x] 4.6 Trim `Development` under the second convention: delete the "you do
      not need a fifth command" explanation and the note on where scope
      markers come from, both already in `AGENTS.md`, which the section
      already links. Confirm they are still there before deleting
- [x] 4.7 Confirm `Development` still carries all four gate commands and every
      pytest selection — only the explaining goes
- [x] 4.8 Confirm nothing was reshaped that was not enumerating, and nothing
      was cut that only the README said

## 5. Move the container detail to its own document

- [x] 5.1 Create `docs/containerized.md` and move into it the five-row flag
      table, the named-volume-versus-bind-mount discussion including the UID
      10001 ownership rule, and the `compose.yaml` and `compose.override.yaml`
      guidance including the leading-`./` trap
- [x] 5.2 Reduce `In a container` to the `docker build` and `docker run`
      commands, the fact that nothing follows the image name because the image
      *is* the run, one sentence naming the durable mount and what is lost
      without it, and the link to the new document
- [x] 5.3 Keep the README's `docker run` to the two flags a run cannot do
      without — `--env-file` and the ledger volume — and leave the optional
      `config.yaml` and enterprise-credential mounts to the new document
- [x] 5.4 Re-point `docs/configuration.md`'s `../README.md#in-a-container`
      link at the new document, where the mount detail now lives
- [x] 5.5 Confirm the durable-mount warning survived the move to the README
      side, since a reader who never follows the link must still meet it

## 6. Confirm

- [x] 6.1 Check every link and anchor the edited sections use still resolves
- [x] 6.2 Read the rendered README start to finish as someone who has not seen
      the codebase, and confirm each new scenario in the delta spec holds
- [x] 6.3 Confirm the extension guide still tells a contributor both kinds
      apart and still points to the guide, which is what the spec requires of
      it and what the rewrite must not lose
- [x] 6.4 Run the four gate commands — they cover no documentation, but a green
      run is what says this change touched nothing it did not mean to
