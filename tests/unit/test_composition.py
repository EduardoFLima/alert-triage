from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from alert_triage.app import composition
from alert_triage.domain.alert import Alert
from alert_triage.domain.report import TriageReport
from alert_triage.ports.config import ConfigError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

# Everything a run needs from its environment, with the ledger in memory and
# the mail relay standing in for whatever a deployment configures.
ENVIRONMENT = {
    "SCOPE_OWNER": "sre",
    "DD_API_KEY": "api-key",
    "DD_APP_KEY": "app-key",
    "ALERT_TRIAGE_LEDGER_PATH": ":memory:",
    "ALERT_TRIAGE_SMTP_HOST": "relay.example",
    "ALERT_TRIAGE_EMAIL_FROM": "triage@example",
    "ALERT_TRIAGE_EMAIL_TO": "sre@example",
}


@dataclass
class FakeAlertSource:
    """Stands in for the adapter that would reach an observability platform."""

    alerts: Sequence[Alert] = ()
    asked_since: datetime | None = None

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Answer with the alerts, remembering that the run got this far."""
        self.asked_since = since
        return self.alerts


@dataclass
class FakeNotifier:
    """Stands in for the fan-out over whatever channels are configured."""

    delivered: list[TriageReport] = field(default_factory=list)

    def deliver(self, report: TriageReport) -> None:
        """Take the report, as a channel that accepted it would."""
        self.delivered.append(report)


@pytest.fixture
def source() -> FakeAlertSource:
    """The alert source the composition root is made to build."""
    return FakeAlertSource(
        [
            Alert(
                service="checkout",
                fired_at=NOON - timedelta(minutes=5),
                source_id="a",
                title="Checkout latency above 2s",
                link="https://platform/event/a",
            )
        ]
    )


@pytest.fixture
def notifier() -> FakeNotifier:
    """The notifier the composition root is made to resolve."""
    return FakeNotifier()


@pytest.fixture
def no_config_file(tmp_path: Path) -> Path:
    """A config path with nothing at it: settings come from the environment."""
    return tmp_path / "config.yaml"


@pytest.fixture
def substituted_adapters(
    monkeypatch: pytest.MonkeyPatch, source: FakeAlertSource, notifier: FakeNotifier
) -> None:
    """Substitute the two adapters that would otherwise leave the process."""
    monkeypatch.setattr(
        composition, "build_alert_source", lambda *args, **kwargs: source
    )
    monkeypatch.setattr(composition, "resolve_notifier", lambda env: notifier)


@pytest.mark.usefixtures("substituted_adapters")
def test_the_composition_root_assembles_a_run_and_executes_it(
    source: FakeAlertSource, notifier: FakeNotifier, no_config_file: Path
) -> None:
    """Configuration, three adapters, and a run — with no integration involved."""
    outcome = composition.execute(now=NOON, env=ENVIRONMENT, config_path=no_config_file)

    (report,) = notifier.delivered
    assert source.asked_since == NOON - timedelta(hours=1)
    assert report.service == "checkout"
    assert outcome.groups == 1
    assert outcome.delivered == 1
    assert outcome.successful


@pytest.mark.usefixtures("substituted_adapters")
def test_the_composition_root_reports_through_the_pass_through_builder(
    notifier: FakeNotifier, no_config_file: Path
) -> None:
    composition.execute(now=NOON, env=ENVIRONMENT, config_path=no_config_file)

    (report,) = notifier.delivered
    assert "not been investigated" in report.body


@pytest.mark.usefixtures("substituted_adapters")
def test_an_incident_opened_by_a_run_is_named_with_a_uuid(
    notifier: FakeNotifier, no_config_file: Path
) -> None:
    """The domain never generates an identifier: this is where they come from."""
    composition.execute(now=NOON, env=ENVIRONMENT, config_path=no_config_file)

    (report,) = notifier.delivered
    assert UUID(report.incident_id)


@pytest.mark.usefixtures("substituted_adapters")
def test_a_missing_scope_refuses_to_start_and_fetches_nothing(
    source: FakeAlertSource, no_config_file: Path
) -> None:
    without_scope = {
        name: value for name, value in ENVIRONMENT.items() if name != "SCOPE_OWNER"
    }

    with pytest.raises(ConfigError, match=r"scope\.owner"):
        composition.execute(now=NOON, env=without_scope, config_path=no_config_file)

    assert source.asked_since is None


def test_a_deployment_with_no_channel_refuses_to_start_and_fetches_nothing(
    monkeypatch: pytest.MonkeyPatch, source: FakeAlertSource, no_config_file: Path
) -> None:
    """A run that could tell nobody what it found has no reason to fetch."""
    monkeypatch.setattr(
        composition, "build_alert_source", lambda *args, **kwargs: source
    )
    without_channel = {
        name: value
        for name, value in ENVIRONMENT.items()
        if not name.startswith("ALERT_TRIAGE_SMTP")
        and not name.startswith("ALERT_TRIAGE_EMAIL")
    }

    with pytest.raises(ConfigError, match="notification channel"):
        composition.execute(now=NOON, env=without_channel, config_path=no_config_file)

    assert source.asked_since is None
