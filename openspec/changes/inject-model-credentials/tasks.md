Each task is one red/green/refactor cycle unless it is plainly not a behavior
change. Write the failing test first and watch it fail.

## 1. Resolve how the model is reached

- [ ] 1.1 Raise the `google-adk` floor in `pyproject.toml` to the version whose
      Gemini model exposes `client_kwargs`, and declare `google-genai` as the
      direct dependency the ADK adapter already imports
- [ ] 1.2 Resolve an API-key deployment from the environment into a value that
      names the key, under both variable names the SDK accepts
- [ ] 1.3 Resolve an enterprise deployment into a value that names the platform
      rather than a key, reading the flag exactly as the SDK reads it
- [ ] 1.4 Carry the enterprise project and location when the environment names
      them, and omit them entirely when it does not
- [ ] 1.5 Refuse, naming both ways of configuring it, when the environment
      supplies neither a key nor the enterprise platform
- [ ] 1.6 Refuse on an exported-but-blank key, as the current check already does
- [ ] 1.7 Retire `require_model_credential` in favour of the resolution, moving
      its tests rather than duplicating them

## 2. Reach the model through what was resolved

- [ ] 2.1 Turn the resolved value into the client arguments each shape allows —
      key alone, or platform with project and location — and never both
- [ ] 2.2 Build the agent's model from those arguments, asserting the client is
      not constructed while doing so
- [ ] 2.3 Widen `build_logs_agent` to take a model name or a built model, with
      its instruction, schema, and tool untouched
- [ ] 2.4 Thread the resolved value from the composition root through
      `run_with_adk` to the agent

## 3. Prove the file reaches the model

- [ ] 3.1 Integration test: a model credential declared only in the run's file,
      never exported, is what the agent's model is built to authenticate with
- [ ] 3.2 Integration test: the enterprise platform selected only in the file
      builds a model that reaches that platform, with no API key present
- [ ] 3.3 Integration test: an exported name still wins over the same name in
      the file

## 4. Document the names

- [ ] 4.1 Add the enterprise project and location to `.env.example` under the
      SDK's own names, with what each is for
- [ ] 4.2 Note in `.env.example` and `docs/vision.md` that a service-account
      path must still be exported, and why this file cannot carry it
- [ ] 4.3 Update the environment section of `docs/vision.md` and the README so
      the documented behavior matches what a run now does

## 5. Close the change

- [ ] 5.1 `uv run ruff check src tests`, `uv run ruff format --check src tests`,
      `uv run mypy`, `uv run pytest` — all four green
- [ ] 5.2 A real run against the `.env` in this checkout reaches the model
      without exporting anything by hand
