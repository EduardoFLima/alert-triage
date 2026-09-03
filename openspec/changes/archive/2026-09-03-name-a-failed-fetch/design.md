## Context

See proposal.md — Why. The relevant constraint is what the vendor SDK actually
lets through, established by reading it rather than assumed:

- `datadog_api_client.rest` catches exactly one urllib3 exception, `SSLError`,
  and re-raises it as `ApiException`. Every other urllib3 failure passes
  through untouched.
- `MaxRetryError`, `NewConnectionError`, `NameResolutionError`,
  `ConnectTimeoutError`, `ReadTimeoutError` and `ProtocolError` all derive from
  `urllib3.exceptions.HTTPError`, which derives from `Exception` — **not** from
  `OSError`. No catch presently in the codebase can intercept them.
- The rest layer also raises `ApiValueError`, a sibling of `ApiException` under
  `OpenApiException`. So the SDK-side gap is in the request path too, not only
  a theoretical one.

## Goals / Non-Goals

**Goals:**

- Every failure of a fetch leaves `DatadogAlertSource` as `AlertSourceError`.
- The translation is pinned by tests that fail first against the present code.

**Non-Goals:**

- Retry or recovery behavior. The SDK already retries under
  `enable_retry`/`max_retries`; this change concerns only how the failure that
  survives retrying is reported.
- Distinguishing kinds of failure in the type system. One error type is what
  the port declares and what the caller needs; the cause is carried in the
  message and by `__cause__`.
- The notification adapters, which already catch `OSError` and so already
  translate their transport failures.

## Decisions

**Catch two roots, not a list of leaves.** `_search` widens to
`except (OpenApiException, urllib3.exceptions.HTTPError)`. `OpenApiException` is
the SDK's own root, so it covers `ApiException` and every sibling; urllib3's
`HTTPError` is that library's root, so it covers every transport failure
enumerated above. The alternative — naming `MaxRetryError` and friends
individually — was rejected because it is a list that goes stale the moment
urllib3 adds a case, and the whole defect being fixed is a too-narrow catch.

**Not `except Exception`.** It would also swallow programming errors in the
translation code below the call, turning a bug into a reported fetch failure.
The two roots are wide enough to be exhaustive and narrow enough to still let a
genuine defect crash.

**`urllib3` is imported by the adapter, and added to the vendor-free-core
contract.** Per AGENTS.md a new runtime dependency joins `forbidden_modules`.
The existing entry `urllib` does not cover it — import-linter matches
top-level package names, and `urllib3` is a different package. The alternative,
inferring the transport error type from the SDK, has no supported route: the
SDK re-exports nothing for this.

**A naming hazard worth one comment.** `urllib3.exceptions.HTTPError` is
urllib3's base for *all* its failures and is unrelated to
`urllib.error.HTTPError`, which the Teams adapter uses to mean "a non-2xx
response". A reader who conflates them will misread the catch as handling
rejections rather than transport, so the import is aliased at the point of use
and carries a comment saying why — comment the *why*, per AGENTS.md.

**The message keeps its present shape.** It already names the owner and
interpolates the underlying error, which is what the delta spec's scenario
asks for; only the set of causes reaching it changes.

## Risks / Trade-offs

**A transport failure now raises `AlertSourceError` where it previously
crashed** → Not a behavior regression in any caller: `execute` already catches
`AlertSourceError` and returns a `RunFailure(Stage.FETCH, ...)`, and `main`
already turns that into exit code 1. The exit code is identical before and
after; only the operator-facing account changes, from traceback to the run's
own. No caller needs editing, which is the evidence this was always a defect
rather than a design gap.

**Pinning a vendor's exception hierarchy in a test** → The tests raise
`MaxRetryError` and `ApiValueError` as the SDK's own layers do, through the
injected `EventSearch` seam, so they need no network and no monkeypatching. If
urllib3 restructures its hierarchy the test fails loudly, which is the correct
outcome for a catch defined in terms of that hierarchy.

**Widening to `OpenApiException` also catches SDK misuse** — `ApiTypeError` from
a request this adapter built wrongly would now be reported as a fetch failure
rather than crashing → Accepted. From the operator's side an unusable request
and an unreachable platform are both "the fetch did not happen", and the
`__cause__` chain preserves the distinction for a developer reading the log.
