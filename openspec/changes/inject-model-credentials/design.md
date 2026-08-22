## Context

See `proposal.md` — Why. The mechanics that shape the approach: `google-genai`
reads `GOOGLE_GENAI_USE_ENTERPRISE`, `GOOGLE_API_KEY`/`GEMINI_API_KEY`,
`GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` from `os.environ` when its
client is constructed, and ADK constructs that client for us. ADK exposes a
`client_kwargs` field on its Gemini model, passed straight to the client
constructor, which is the seam this change uses.

## Goals / Non-Goals

**Goals:**
- The environment a run resolved is the only environment the model is reached
  through.
- The startup refusal and the model client are built from one value, so they
  cannot disagree.

**Non-Goals:**
- Proving at startup that the credential *works*. The check answers whether a
  run could authenticate at all, not whether the account is entitled to the
  model.
- Application default credentials. See Risks.

## Decisions

**Inject into the model client; do not export into the process environment.**
The alternative — `os.environ.update(...)` at startup — is one line and would
fix every library at once, including the credential discovery this change
leaves alone. It was rejected because the composition root's whole shape is
"resolve a value, hand it down"; mutating process globals to communicate with a
library inverts that, and makes the run's configuration invisible at the point
it is used.

**Resolve an access value; let the check fall out of it.** Rather than keeping
a boolean check beside a separately-constructed client, the ADK adapter gains a
frozen value describing how the model is reached, resolved from the
environment the same way `DatadogConnection` already is. The refusal becomes
"this could not be resolved" instead of a rule that must be remembered to agree
with the client built later.

**The resolver decides the platform; the client is never given a choice.** The
SDK rejects a project or location without the enterprise flag, and rejects
credentials and an API key together. Passing everything through and letting the
SDK sort it out would move those errors to the first investigation. The
resolved value is therefore one shape or the other, and carries only the keys
that shape allows.

**Use `client_kwargs`, not a subclass.** The SDK also documents overriding the
`api_client` property on a `Gemini` subclass. `client_kwargs` is a plain field
that keeps the model a value rather than a type, which keeps it constructible
in a unit test. The subclass remains the fallback if the field is withdrawn.

**Build the model beside the credential, not inside the agent.** `logs_agent`
widens from a model name to a name-or-model, and nothing else about it changes;
what a model costs to reach is not the Logs specialist's concern, and its unit
tests stay free of the SDK's model types.

**The composition root builds the model.** The alternative was to hand
`run_with_adk` the resolved access and let the ADK adapter build the model on
first use, which would keep ADK unimported by a run that never investigates.
It was rejected on two counts: naming concrete adapters is precisely the
composition root's job, and a model built behind a closure is a model no test
can look at. ADK is now imported at startup rather than at the first incident.

**Keep the client lazy.** ADK builds it on first use, and forcing it at startup
would run credential discovery — file and network I/O — before the run has
decided it needs a model. The existing startup refusal already catches the
misconfiguration that matters.

## Risks / Trade-offs

- **Application default credentials still read the process environment.** An
  enterprise deployment whose service-account path is set only in the run's
  file, and never exported, still will not be found — the same class of bug one
  layer down. → Documented in `.env.example` and `docs/vision.md` as the one
  name that must be exported; not silently narrowed.
- **The declared dependency floor is too low.** `google-adk>=1.16` predates the
  field this design depends on (installed: 2.7.1). → Raise the floor as part of
  the change, so an install that resolves to an older ADK fails at install time
  rather than by silently ignoring the injected settings.
- **Startup still cannot prove the account works.** A resolvable but wrong
  project fails on the first investigation. → Unchanged from today, and out of
  scope; the failure is already reported as an investigation failure rather
  than a silent one.

## Migration Plan

Additive. The resolved environment is the process environment plus the file, so
a deployment that exports everything today resolves to exactly the same values
and is unaffected. Only deployments that were already broken change behavior.
