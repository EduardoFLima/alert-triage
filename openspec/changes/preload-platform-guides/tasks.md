## 1. Matching and naming guides

- [x] 1.1 Red/green: a guide naming a permitted tool is matched to that specialist
- [x] 1.2 Red/green: a guide naming only other tools is not matched
- [x] 1.3 Red/green: matching is whole-word, so a tool name inside a longer one does not match
- [x] 1.4 Red/green: a specialist with two toolsets is matched on tools from either
- [x] 1.5 Red/green: a Datadog guide name that is not kebab-case becomes one ADK accepts
- [x] 1.6 Red/green: a guide that mentions a permitted tool without documenting it under a heading is not matched (revised by 2.1: mention-matching offered every specialist 9–23 guides)

## 2. Fetching guides at startup

- [x] 2.1 Read one real listing and guide (by hand, with the user) to settle names, descriptions, and how a guide names a further reference — findings in design.md, "What the platform publishes"
- [x] 2.2 Red/green against a fake MCP server: every listed guide is fetched with its description, and its references one level deep
- [x] 2.2a Red/green: a load the server refuses is retried after a pause, and a guide still refused is left out with a warning
- [x] 2.3 Red/green: fetched guides become ADK `Skill` objects, references in `Resources.references`
- [x] 2.4 Red/green: an unreachable server yields no guides and a single warning, not an exception
- [x] 2.5 Red/green: the fetch is bounded by `mcp_call_timeout_seconds`
- [x] 2.6 Red/green: `build_investigator` fetches once and hands the guides to the deployment; nothing is written to disk

## 3. Offering guides to agents

- [x] 3.1 Red/green: `build_agent` gives a specialist a `SkillToolset` holding only its matched guides, filtered to `load_skill` and `load_skill_resource`
- [x] 3.2 Red/green: the declaration's instruction is passed unchanged; no guide text is in it
- [x] 3.3 Red/green: loading an unheld guide returns `SKILL_NOT_FOUND`
- [x] 3.4 Red/green: a load neither uses the specialist's tool budget nor becomes evidence
- [x] 3.5 Red/green: a specialist with no matched guides gets no `SkillToolset`
- [x] 3.6 Red/green: an investigation run without guides is not marked incomplete for that reason

## 4. Taking browsing away

- [x] 4.1 Invert `test_every_specialist_can_consult_the_platforms_guidance`: no specialist permits either Datadog skill tool
- [x] 4.2 In one commit, remove both skill tools from every toolset and remove `CONSULT_THE_PLATFORM` from every instruction, test first. Removing the text before the toolsets fails `test_a_declaration_and_its_instruction_agree`, because the skill tools would be permitted but no longer named
- [x] 4.3 Update the query-dialect bullet under "A Datadog integration that holds up" in `docs/vision.md`

## 5. Verification

- [ ] 5.1 Live suite: each specialist is offered at least one guide (credential-gated; the user runs it)
- [ ] 5.2 Record which guides each specialist is offered and loads, and the size of ADK's added instruction, from that run
- [ ] 5.3 If the metrics guide covers the grammar rules in `METRIC_QUERY_DIALECT`, delete those rules and their assertions in a separate commit. Keep the refused-aggregation rule and `AN_EMPTY_ANSWER`
- [x] 5.4 Run ruff check, ruff format --check, mypy and pytest
