## Why

A run resolves its environment once — the process environment supplemented by
an optional `.env` file — and hands that mapping to every adapter. The Google
GenAI SDK is the one consumer that cannot take it: it reads `os.environ`
itself. So model settings placed in `.env` and not exported are silently
ignored, while the startup credential check, which reads the resolved mapping,
passes anyway. A deployment that cannot authenticate starts, fetches alerts,
and fails on its first investigation — the exact failure that check exists to
prevent.

## What Changes

- How an investigation authenticates its model is **resolved** from the
  environment the run resolved, and injected into the ADK model client, rather
  than left for the SDK to rediscover from the process environment.
- The startup check becomes that resolution: it can no longer pass in a state
  the model client would reject, because the value it produces is the value the
  client is built from.
- The enterprise platform's project and location join the API key as
  first-class, documented deployment facts.
- The Logs agent is built around a model that carries this access rather than a
  bare model name. Its instruction, output schema, and tool are untouched.
- Out of scope: application default credentials. `GOOGLE_APPLICATION_CREDENTIALS`
  and the gcloud well-known file are read by `google-auth` from the process
  environment, and a service-account path set only in `.env` still will not be
  found. The boundary is named in `design.md`.

## Capabilities

### Modified Capabilities

- `config`: the environment a run resolves — process plus optional file — is
  the single environment every setting and credential is read from, with no
  consumer reading the process environment behind it.
- `investigation`: the credential an investigation's model reasons on is
  injected into the model client rather than discovered by it, and the refusal
  to start agrees with what that client would actually do.

## Impact

- `adapters/adk/credentials.py` — from a check to a resolution.
- `adapters/adk/logs_agent.py`, `adapters/adk/investigator.py`,
  `app/composition.py` — the resolved access reaches the agent's model.
- `.env.example`, `docs/vision.md`, `README.md` — the enterprise variables
  become documented names.
- No new dependency: `google-genai` already arrives with `google-adk` and is
  already imported directly by the ADK adapter.
