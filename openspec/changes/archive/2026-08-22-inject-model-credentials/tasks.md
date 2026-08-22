Each task is one red/green/refactor cycle unless it is plainly not a behavior
change. Write the failing test first and watch it fail.

## 1. Resolve how the model is reached

- [x] 1.1 Raise the `google-adk` floor in `pyproject.toml` to the version whose
      Gemini model exposes `client_kwargs`
- [x] 1.2 Resolve an API-key deployment from the environment into a value that
      names the key, under both variable names the SDK accepts
- [x] 1.3 Resolve an enterprise deployment into a value that names the platform
      rather than a key, reading the flag exactly as the SDK reads it
- [x] 1.4 Carry the enterprise project and location when the environment names
      them, and omit them entirely when it does not
- [x] 1.5 Refuse, naming both ways of configuring it, when the environment
      supplies neither a key nor the enterprise platform
- [x] 1.6 Refuse on an exported-but-blank key, as the current check already does
- [x] 1.7 Retire `require_model_credential` in favour of the resolution, moving
      its tests rather than duplicating them

## 2. Reach the model through what was resolved

- [x] 2.1 Turn the resolved value into the client arguments each shape allows —
      key alone, or platform with project and location — and never both
- [x] 2.2 Build the agent's model from those arguments, asserting the client is
      not constructed while doing so
- [x] 2.3 Widen `build_logs_agent` to take a model name or a built model, with
      its instruction, schema, and tool untouched
- [x] 2.4 Build the model in the composition root from the resolved value, and
      hand it to `run_with_adk` already told how to authenticate

## 3. Prove the file reaches the model

- [x] 3.1 Integration test: a model credential declared only in the run's file,
      never exported, is what the agent's model is built to authenticate with
- [x] 3.2 Integration test: the enterprise platform selected only in the file
      builds a model that reaches that platform, with no API key present
- [x] 3.3 Integration test: an exported name still wins over the same name in
      the file

## 4. Document the names

- [x] 4.1 Add the enterprise project and location to `.env.example` under the
      SDK's own names, with what each is for
- [x] 4.2 Note in `.env.example` and `docs/vision.md` that a service-account
      path must still be exported, and why this file cannot carry it
- [x] 4.3 Update the environment section of `docs/vision.md` and the README so
      the documented behavior matches what a run now does

## 5. Close the change

- [x] 5.1 `uv run ruff check src tests`, `uv run ruff format --check src tests`,
      `uv run mypy`, `uv run pytest` — all four green
- [x] 5.2 The `.env` in this checkout reaches the model without exporting
      anything by hand — verified by building the model and its client from a
      process that exported nothing, rather than by a full run, which would
      fetch alerts and notify the configured channels
