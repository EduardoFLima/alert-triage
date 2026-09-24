## 1. The catalogue

- [x] 1.1 Red/green: `DatadogTool` holds a name, a toolset and a description, and rejects an empty one
- [x] 1.2 Red/green: `toolsets(...)` groups tools by toolset in first-seen order, each with `provider=DATADOG`
- [x] 1.3 Red/green: `described(...)` renders each tool as a ``- `name` description`` bullet, in the order given
- [x] 1.4 Add every tool the crew permits today to `datadog/tools.py`, with the toolset it is declared in today
- [x] 1.5 Move `SKILL_LIST_TOOL` and `SKILL_LOAD_TOOL` from `dialect.py` into the catalogue
- [x] 1.6 Red/green: no two catalogue tools share a name, and every catalogue tool is permitted by some specialist

## 2. Specialists pick from it

- [x] 2.1 Logs: toolsets and tool list from the catalogue; existing tests green
- [x] 2.2 Infrastructure: same; its host-tag sentence stays in its instruction
- [x] 2.3 APM: same, for both Preview branches; its catalogue-search guidance stays in its instruction
- [x] 2.4 Trace: same, for both Preview branches
- [x] 2.5 Delete the per-specialist tool and toolset constants that are now unused

## 3. Verification

- [x] 3.1 Diff each specialist's rendered instruction before and after; list every changed sentence in the commit message
- [x] 3.2 Run ruff check, ruff format --check, mypy and pytest
- [ ] 3.3 Live suite, once (credential-gated; the user runs it)
