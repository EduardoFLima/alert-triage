## 1. Matching guides to specialists

- [ ] 1.1 Red/green: a guide naming a permitted tool is matched to that specialist
- [ ] 1.2 Red/green: a guide naming only other tools is not matched
- [ ] 1.3 Red/green: matching is whole-word, so a tool name inside a longer one does not match
- [ ] 1.4 Red/green: a specialist with two toolsets is matched on tools from either

## 2. Fetching guides

- [ ] 2.1 Read one real guide (by hand, with the user) to settle how a guide names a further reference
- [ ] 2.2 Red/green against a fake MCP server: every listed guide is loaded, and references are followed one level deep
- [ ] 2.3 Red/green: an unreachable server yields no guides and a single warning, not an exception
- [ ] 2.4 Red/green: the fetch is bounded by `mcp_call_timeout_seconds`

## 3. Giving guides to agents

- [ ] 3.1 Red/green: `build_agent` sets the instruction to the declaration's instruction followed by its matched guides
- [ ] 3.2 Red/green: the declaration itself is unchanged after an agent is built
- [ ] 3.3 Red/green: guides are fetched on the first investigation of a run and reused by the next
- [ ] 3.4 Red/green: an investigation run without guides is not marked incomplete for that reason

## 4. Taking the skill tools away

- [ ] 4.1 Invert `test_every_specialist_can_consult_the_platforms_guidance`: no specialist permits the list or load skill tools
- [ ] 4.2 In one commit, remove the skill tools from every toolset and replace `CONSULT_THE_PLATFORM` with the "guides may mention tools you do not have" line, test first. Changing the text before the toolsets fails `test_a_declaration_and_its_instruction_agree`, because the skill tools would be permitted but no longer named
- [ ] 4.3 Update the query-dialect bullet under "A Datadog integration that holds up" in `docs/vision.md`

## 5. Verification

- [ ] 5.1 Live suite: each specialist is matched to at least one guide (credential-gated; the user runs it)
- [ ] 5.2 Record guide sizes from that run
- [ ] 5.3 If the metrics guide covers the grammar rules in `METRIC_QUERY_DIALECT`, delete those rules and their assertions in a separate commit. Keep the refused-aggregation rule and `AN_EMPTY_ANSWER`
- [ ] 5.4 Run ruff check, ruff format --check, mypy and pytest
