## Why

One service is usually deployed to several environments, and today nothing in
`scope` says which one a run watches. A `checkout` alert from staging is
fetched, grouped and reported exactly like one from production, and the
investigation that follows gathers evidence across every environment the
service runs in. A report about production can rest on staging's logs, and a
link under it can open a view that mixes the two.

## What Changes

- **`scope.env` names the environment a run watches**, resolved from the file
  or `SCOPE_ENV`, defaulting to `prod`. One environment per deployment; a
  second environment is a second deployment. It narrows the owner and services
  filters rather than satisfying scope on its own, so `scope` stays mandatory
  and "watch all of prod" is still refused.
- **Only alerts from that environment are fetched.** The alert source adds the
  platform's environment term to its query, the same way it spends owner and
  services.
- **An alert's link stays inside the environment** where the link is a view of
  the service rather than of the monitor, so a reader is not shown other
  environments' alerts beside the one that fired.
- **An investigation is told the environment**, as part of its target beside
  the service, the window and criticality. The description handed to the crew
  states it, and the specialists are told to scope every query to the service
  *and* the environment.
- **Evidence addresses carry the environment.** An address copied from a
  retrieval keeps whatever query was actually run, environment and all — it is
  not rewritten, because it has to open what was retrieved. An address the
  system *composes* from the target (the APM service page and trace explorer
  forms proposed in `address-evidence-where-it-came-from`, and a finding's
  service-page link) SHALL include the environment, or it opens a page scoped
  to every environment of the service.
- **A report names the environment** of the incident it is about.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config`: `scope` gains `env`, defaulted to `prod`, which narrows but never
  satisfies scope on its own.
- `alert-ingestion`: the scope filter gains the environment; a service-scoped
  alert link is narrowed to it.
- `investigation`: the target carries the environment; an address composed
  from the target carries it too.
- `triage-run`: a report names its incident's environment.

## Impact

- Code: `configuration/settings.py` and `configuration/adapters/yaml/loader.py`;
  `triage/adapters/datadog/alert_source.py` and its builder in
  `app/composition.py`; `triage/domain/incident.py`; `investigation/contract.py`
  (`InvestigationTarget`); `investigation/adapters/datadog/dialect.py` and the
  specialists' instructions; `investigation/adapters/datadog/links.py` for any
  composed form; the report builder in `triage`.
- Docs: `config.example.yaml`, `docs/configuration.md`, and the config section
  of `docs/vision.md`.
- Ledger: no schema change. Incidents stay keyed by service; see design.md for
  why a changed `SCOPE_ENV` is a changed deployment.
- Live: the specialists' instructions change, so the credential-gated tests in
  `docs/live-testing.md` are the only proof their queries still resolve.
- Coordinates with the in-flight `address-evidence-where-it-came-from`: whichever
  lands second adds the environment to the composed forms.

## Out of Scope

- **Several environments in one run.** A list would reopen grouping (is
  `checkout` in prod and in staging one incident?) and the report subject. One
  value keeps both untouched.
- **Reading the environment off each alert.** Every fetched alert is already
  in the configured environment; see design.md.
- **A monitor link scoped to the environment.** The monitor page is the
  monitor's own, and a group filter on it is not a documented address form.
