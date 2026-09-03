## Why

`alert-ingestion` already requires that a fetch which fails because "the
platform is unreachable" raises an error identifying the failure, and
`triage-run` already requires that a failed fetch ends the run "naming the
failure". Neither holds today. The Datadog adapter translates the SDK's
`ApiException` into `AlertSourceError`, but a transport failure — DNS, TLS, a
refused connection, retries exhausted — surfaces as `urllib3.MaxRetryError`,
which is not an `ApiException` and not an `OSError`. It escapes the adapter,
escapes the pipeline's `except AlertSourceError`, and reaches the operator as a
raw traceback from Python's default handler.

The exit code is still 1, so a scheduler is unharmed. A human is not: the one
failure mode the run's own account was built for is the one it never explains.

The requirement's prose has been right since the capability was written. What
was missing is a scenario pinning it, which is why nothing caught the omission.

## What Changes

- The Datadog alert source translates transport failures into
  `AlertSourceError`, so an unreachable platform is named by the run rather
  than by a traceback.
- It also translates the SDK's other `OpenApiException` subclasses
  (`ApiTypeError`, `ApiValueError`, `ApiAttributeError`, `ApiKeyError`). The
  adapter catches `ApiException` alone today, so a payload the SDK cannot
  model escapes by the same route as a transport failure.
- `alert-ingestion` gains scenarios for both, so the requirement that already
  covers them is shown to fail before it is made to pass.
- `urllib3` joins the `forbidden_modules` of the vendor-free-core contract in
  `.importlinter`. The list holds `urllib`, which does not cover it — a
  different top-level package.

Not in scope: the notification adapters, which already translate transport
failures correctly by catching `OSError` (`urllib.error.URLError` and
`smtplib`'s socket failures both derive from it). This is the alert source
alone.

## Capabilities

### New Capabilities

None. The behavior is already specified; this change makes it true.

### Modified Capabilities

- `alert-ingestion`: the requirement "A failed fetch is reported, not
  disguised" gains scenarios for an unreachable platform and for a response the
  SDK cannot model. Its prose is unchanged — both cases already fall under it.

## Impact

- `src/alert_triage/triage/adapters/datadog/alert_source.py` — `_search`
  widens what it translates.
- `.importlinter` — `urllib3` added to `forbidden_modules`.
- `tests/unit/triage/adapters/datadog/test_alert_source.py` — new failing
  tests first.
- No change to the `AlertSource` port, to `AlertSourceError`, to the pipeline,
  or to any exit code. Callers already handle the error this change starts
  raising, which is the whole point.
