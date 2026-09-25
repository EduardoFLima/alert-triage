## Why

Datadog's MCP server answers several of its tools with a block of text — a
`<METADATA>` preamble and a `<TSV_DATA>` table — rather than with JSON. The
evidence reader finds items in a list, or in a list under a known envelope key,
and a text block is neither, so it yields none. A live log search that returned
sixty error lines under two patterns was cited as one whole retrieval: no
`call-N/item-M`, no per-item address, and a summary that is the first three
hundred characters of the server's description of the answer instead of the
answer. The credential-gated run in `address-evidence-where-it-came-from`
skipped its item test over this and said the logs had been quiet, which was not
true.

The same block carries the server's own composed address for the view it ran —
`logs_explorer_url`, pinned to the pattern visualisation with its clustering
field and aggregation — which is a better address than the one this project
composes, and is being discarded along with the rest of the text.

## What Changes

- **The reader learns the text-table shape.** A result whose text carries a
  `<TSV_DATA>` table yields one item per row, keyed by the table's own header,
  alongside the two shapes it already reads. It stays platform-blind: a table
  with a header and rows is a shape, not a Datadog tool.
- **A retrieval is addressed by the server where the server addressed it.** An
  address the platform returned with the answer wins over one composed from the
  tool and its arguments, because the server knows which view it ran and this
  project can only infer it. A composed address remains the fallback.
- **`ITEM_KEYS` is settled against real payloads.** The previous change left
  which key a live item is identified under as an open question, because no
  live payload ever reached `to_item`. Now one will.
- **The live item test stops misreporting why it skipped.** "The logs were
  quiet" was the wrong diagnosis; a skip states the condition it actually
  found.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `investigation`: evidence identified at item grain from a platform that
  answers in text, and precedence between an address the platform returned and
  one this project composed.

## Impact

- `investigation/adapters/adk/normalisation.py` — reading items and summaries.
- `investigation/adapters/adk/evidence.py` — where an address is asked for.
- `investigation/adapters/datadog/links.py` — `ITEM_KEYS`, and yielding to a
  returned address.
- `tests/integration/investigation/adapters/datadog/` — the live item test's
  skip condition.

Out of scope: which page a retrieval is addressed to when this project does
compose one — that is `address-metrics-by-what-they-describe`.
