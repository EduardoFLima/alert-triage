Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

Tasks 1 and 2 are independent of each other: the first restores item grain,
the second restores the right address. Task 3 widens the port both of them
reach through, so it comes after the shape of what they need is settled. Task
5 is the only one that can settle `ITEM_KEYS`, and it needs credentials.

## 1. A table of text yields its rows

- [ ] 1.1 In `tests/unit/investigation/adapters/adk/test_items_are_read_out_of_any_result.py`,
  assert a result whose text is a header row over two delimited rows yields two
  items, each summarised from its own row. Teach `_items` in
  `adk/normalisation.py` the table shape, beside the list and the envelope.
- [ ] 1.2 In the same file, assert a row's values are readable in its payload
  under the header's own column names, so a finding citing `call-N/item-M`
  carries what that row said and not the raw line.
- [ ] 1.3 Assert text carrying no rows — one line, or prose — still yields no
  items and leaves the retrieval citable whole. The fallback is the behaviour
  that exists today and must survive.
- [ ] 1.4 Assert a `<METADATA>` preamble before the table is not read as a row,
  and that the table is found whether or not the `<TSV_DATA>` marker is there.
  Markers locate the table; their absence does not stop the read.
- [ ] 1.5 Assert a row whose column count does not match the header is not read
  as an item. A mismatch means the text was not the table it looked like.

## 2. The platform's own address wins

- [ ] 2.1 In `tests/unit/investigation/adapters/datadog/test_evidence_is_addressed_where_it_lives.py`,
  assert a retrieval carrying an address the platform composed is addressed by
  that address rather than by the template for its tool.
- [ ] 2.2 In the same file, assert a retrieval carrying none is addressed
  exactly as it is today, by the template for its tool. Every existing address
  test must come out the other side unchanged.
- [ ] 2.3 Assert a URL sitting in the body of a retrieval — a log line quoting
  one — is not taken as the platform addressing its answer. Only the place the
  platform puts its address is read.
- [ ] 2.4 Assert an item within a retrieval addressed by the platform falls
  back to that address, not to the composed one, so the two grains agree.

## 3. The port is told what came back

- [ ] 3.1 In `tests/unit/investigation/adapters/adk/test_only_what_was_retrieved_is_citable.py`,
  assert `retain_evidence` hands the linker the result as well as the tool and
  its arguments. Widen `Links.to_retrieval` in `adk/evidence.py` and thread the
  result through `_address_of`.
- [ ] 3.2 In the same file, assert a `Retrieved` built without a linker still
  keeps every `url` at `None`, and that a failed retrieval is still refused
  before any address is asked for.
- [ ] 3.3 Run the architecture test and confirm `adk/` still has no import of
  `datadog/`. The result is `Any` across the seam; if this cycle needed an
  import, the linker has stopped being injected.

## 4. The report shows what changed

- [ ] 4.1 In the report's own tests, assert a finding citing items from a
  text-answered retrieval renders one line per item with its own summary,
  rather than one line carrying a truncated preamble.

## 5. Against a real account

- [ ] 5.1 Correct the skip message in
  `tests/integration/investigation/adapters/datadog/test_every_specialist_reaches_the_real_platform.py`:
  it currently says the logs were quiet when the condition it found was that no
  items could be read. A skip states what it actually found.
- [ ] 5.2 Run the credential-gated suite against a service known to be noisy
  and assert the log search now yields items. Record the payload of one in the
  task list — it is the evidence that settles 5.3.
- [ ] 5.3 Settle `ITEM_KEYS` in `datadog/links.py` from that payload: keep the
  keys a live item is identified under, drop the ones nothing uses, and say in
  the docstring which live run answered it. A key with no payload behind it is
  the guess the previous change declined to make.
- [ ] 5.4 Record which tools returned an address of their own and under which
  key, and confirm each of those addresses opens. An address preferred over a
  composed one has to be at least as good as the one it replaced.
- [ ] 5.5 Run the full gate — `ruff check`, `ruff format --check`, `mypy`,
  `pytest` — and say plainly which of 5.2 to 5.4 were run against real
  credentials and which were not.
