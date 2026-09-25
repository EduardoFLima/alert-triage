## Context

See proposal.md — Why. Two facts about the code shape the approach.

`normalisation.py` reads items without knowing which platform answered: a list,
or a list under one of a few envelope keys. It is deliberately shallow because
a specialist discovers its tools at runtime and there is no catalogue to write
a reader against.

`Links.to_retrieval` is given the tool and the arguments it was called with —
not the result. The address the platform composed arrives in the result, so
preferring it is not a change of rule inside the adapter; it is a change to
what the port is told.

## Goals / Non-Goals

**Goals:** items out of a text table; a returned address preferred over a
composed one; `ITEM_KEYS` settled against a live payload.

**Non-Goals:** knowing which Datadog tools answer in text. The reader keys off
the shape of the answer, so a tool that switches encodings needs no edit here.
Nothing about which page a composed address opens.

## Decisions

**The table reader lives in `normalisation.py`, beside the two shapes already
read.** The alternative is a Datadog-side reader that hands structured data
across, which keeps `normalisation.py` untouched but makes the second platform
write its own reader for a shape that is not Datadog's invention. A header row
over delimited rows is a shape, like a list is a shape; `ENVELOPE_KEYS` is
already this file admitting it knows a little about how platforms wrap things.

**The `<METADATA>` and `<TSV_DATA>` markers are recognised, not required.** The
reader looks for a delimited table and reads a header from its first row. A
marker present is a strong signal and is used to find the table's bounds; a
marker absent does not stop the read. The alternative — matching Datadog's
exact preamble — turns a server-side format tweak into zero items again, which
is the failure being fixed.

**`to_retrieval` is given the result as well as the arguments.** The port grows
one parameter. The alternative is a separate `address_returned_by(result)` that
the caller tries first, which leaves the precedence rule in the framework
adapter — the place that is meant to know nothing about a platform's addresses.
Precedence between two addresses for the same retrieval is the platform
adapter's judgement, so the platform adapter should see both.

**A returned address is taken only from where the platform put it, and is
validated as an address.** It arrives in the same text as the evidence, so a
log line quoting a URL must not be mistaken for the platform addressing its
answer. The alternative — the first URL-shaped thing in the text — is how a
reader gets sent to an address an attacker or a stack trace put there.

**`ITEM_KEYS` is settled by running the live suite and reading a payload, not
by widening the list speculatively.** A key added without a payload behind it
is the same unverified guess the previous change declined to make.

## Risks / Trade-offs

**A text answer whose rows are not a table** (prose that happens to contain
tabs) → items appear where there are none. Mitigated by requiring a header row
and a consistent column count, and by the fallback being the current behaviour:
cite the retrieval whole.

**Datadog changes the text format** → the reader silently goes back to zero
items, which looks like an aggregate rather than like a failure. Mitigated by
the live suite asserting items are extracted for a service known to be noisy,
so the regression fails a test rather than degrading a report.

**Widening the port's signature touches every implementation and fake.** Small
and contained: one adapter, one protocol, the fakes in the unit tests.

## Open Questions

Which tools other than the log search return an address of the platform's own,
and under which key. Answerable from the live run during implementation; the
rule does not change either way, only the set of tools it fires for.
