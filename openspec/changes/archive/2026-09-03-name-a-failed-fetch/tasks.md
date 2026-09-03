## 1. Red — pin the transport failure

- [x] 1.1 Add a unit test to
  `tests/unit/triage/adapters/datadog/test_alert_source.py` driving the
  existing `_source(...)` helper with a `urllib3.exceptions.MaxRetryError` and
  asserting `AlertSourceError` naming the owner. Run it and watch it fail with
  the raw `MaxRetryError` escaping — this is the reported defect, reproduced.
- [x] 1.2 Add a second test raising the failure on a later page, so the
  transport case is pinned on the pagination path too and not only the first
  request.
- [x] 1.3 Add a test raising `ApiValueError` — the sibling the SDK's own rest
  layer raises — and watch it fail for the same reason.

## 2. Green — widen the translation

- [x] 2.1 In `_search`, widen the catch to
  `(OpenApiException, urllib3.exceptions.HTTPError)`, importing urllib3's
  exception module aliased at the point of use with the comment explaining it
  is unrelated to `urllib.error.HTTPError`. Confirm the three tests pass and
  the rest of the file stays green.
- [x] 2.2 Confirm `raise ... from error` still chains, so `__cause__` carries
  the original for a developer reading the log.

## 3. Keep the boundary enforced

- [x] 3.1 Add `urllib3` to `forbidden_modules` of the vendor-free-core contract
  in `.importlinter`.
- [x] 3.2 Show that contract can fail: temporarily import urllib3 from
  `triage/domain` or `triage/ports`, run `uv run pytest
  tests/unit/test_architecture.py`, confirm it names the offending module, then
  revert. A contract never shown to fail has not been shown to enforce
  anything.

## 4. Prove it against the real stack

- [x] 4.1 Add an integration test under
  `tests/integration/triage/adapters/datadog/` that builds the real client via
  `build_alert_source` against an unresolvable site with dummy credentials and
  asserts `AlertSourceError`. It exercises the actual SDK and urllib3 rather
  than a hand-raised exception, needs no valid credentials — the request never
  reaches authentication — and so does not skip. This is what catches a future
  urllib3 restructuring.
- [x] 4.2 Keep its timeout and retry bound small so the test stays fast.

> **Deviation from 4.1 as planned.** The test does not go through
> `build_alert_source`. The SDK validates `site` against its own list of real
> regions and raises `ValueError` on an unknown one before any request, so an
> unresolvable site cannot be supplied through `DatadogConnection`. The test
> instead uses the production `build_configuration` — keeping the real timeout
> and retry bounds — and overrides `configuration.host`, then assembles the
> real `ApiClient` and `EventsApi`. The intent of 4.1 is met in full: the
> failure caught is one urllib3 genuinely raised, confirmed by narrowing the
> catch again and watching both tests fail with a raw `MaxRetryError`.
> The SDK's site validation is good behavior and was left alone.

## 5. Confirm the operator-facing account

- [x] 5.1 Verify by inspection that `execute` maps the now-raised error to
  `RunFailure(Stage.FETCH, ...)` and `main` logs "a stage of the run failed"
  and returns `FAILURE`. Expect no edits here; if any are needed, the defect
  was wider than diagnosed — say so rather than widening the change silently.
- [x] 5.2 Confirm the exit code is 1 both before and after, so only the
  account changed and no scheduler behavior did.

## 6. Before calling it done

- [x] 6.1 Run `uv run ruff check src tests`,
  `uv run ruff format --check src tests`, `uv run mypy`, and `uv run pytest`.
  All four must pass.
- [x] 6.2 State plainly which live tests were and were not run — per
  `docs/live-testing.md`, no credentialed run is needed for this change, and
  task 4.1's test is deliberately one that does not need them.
