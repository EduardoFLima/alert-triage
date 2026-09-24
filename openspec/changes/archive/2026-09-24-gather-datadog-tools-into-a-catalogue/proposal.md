## Why

What a Datadog tool is — its name, the toolset serving it, and what it does —
is scattered across the four specialist modules:

- The three metric tools are declared twice, in `apm.py` and
  `infrastructure.py`, and described twice in nearly the same words.
- The `core` toolset is spelled out four times under three names
  (`CORE_TOOLSET`, and `LOGS_TOOLSET` in `logs.py`); `apm` twice.
- Each specialist hand-assembles its `Toolset(provider=DATADOG, name=...,
  tools=...)`, so nothing stops a tool being put in the wrong toolset.
- The instruction's "the tools you have" list is written separately from the
  toolsets, and only `test_a_declaration_and_its_instruction_agree` keeps the
  two in step.

A tool's facts belong to the provider, and should be stated once.

## What Changes

- **A Datadog tool catalogue**, in `investigation/adapters/datadog/tools.py`.
  Each tool is one value holding its name, its toolset, and a one-line
  description of what it does. The skill tools move there from `dialect.py`.
- **Specialists pick tools from the catalogue.** A declaration lists the tools
  it permits; its toolsets are derived from them, and its "the tools you have"
  list is rendered from the same values. What a specialist asks for, in what
  order, and what it reports stay in the specialist.
- **No behaviour change intended.** Where two specialists describe the same
  tool differently today, the shared description keeps the common part and the
  difference stays in that specialist's instruction.

Out of scope:

- Query grammar (`METRIC_QUERY_DIALECT`, and the log and span grammar inline in
  `logs.py` and `trace.py`). `preload-platform-guides` sources grammar from
  Datadog's own guides; moving it first would be moving it twice.
- The Preview switch. `preview.py` keeps it; the catalogue only records which
  toolset a tool is in.

This change should land before `preload-platform-guides`, which edits the same
toolsets.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. A refactor: no requirement changes, so `skip_specs` is set.

## Impact

- New: `investigation/adapters/datadog/tools.py`.
- Changed: the four modules in `investigation/adapters/crew/specialists/`, and
  `datadog/dialect.py` (loses the skill tool names).
- Instruction text changes only where two descriptions of one tool are merged.
  That is a change to what the model reads, so a live run should confirm it.
- Tests: unit tests for the catalogue; existing specialist tests stay as the
  guard that nothing a specialist permits or is told has changed.
