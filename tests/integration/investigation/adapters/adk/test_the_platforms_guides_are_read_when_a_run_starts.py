"""The platform's guides are read once, when a run starts, over a real socket.

A fake MCP server stands in for the platform and speaks the way the real one
was read to: a listing with headers, a load per guide, a load per bundled
reference, and every call carrying the telemetry the real server requires.
"""

import logging
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.agent import Deployment, PlatformAccess
from alert_triage.investigation.adapters.adk.guides import fetch_guides
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide
from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

LISTING = """\
- **datadog/logs**: Load this skill when searching logs. (related: datadog/ddsql)
  Resources: references/log-syntax.md
- **datadog/metrics**: Load this skill when querying metrics.
  Resources: references/metric-syntax.md
"""

TEXTS = {
    "datadog/logs": "# Logs\n\n## Tools\n\n### search_datadog_logs\n\nSearch.",
    "datadog/metrics": "# Metrics\n\n## Tools\n\n### get_datadog_metric\n\nQuery.",
}
REFERENCES = {
    ("datadog/logs", "references/log-syntax.md"): "Quote a value with spaces.",
    ("datadog/metrics", "references/metric-syntax.md"): "avg:name{scope}",
}


class _Report(BaseModel):
    summary: str


LOGS = Specialist(
    name="logs_specialist",
    signal=Signal.LOGS,
    instruction="Search the logs.",
    output_schema=_Report,
    toolsets=(Toolset(DATADOG, "core", ("search_datadog_logs",)),),
)


class _Platform:
    """What the fake was asked, and how it is told to misbehave."""

    def __init__(self) -> None:
        self.loads: list[tuple[str, str | None]] = []
        self.refusals: dict[str, int] = {}
        self.listing_delay_seconds = 0.0

    def server(self) -> FastMCP:
        mcp = FastMCP("fake-datadog")

        @mcp.tool(name="list_datadog_skills")
        def listing(telemetry: dict[str, str], include_header: bool = False) -> str:
            """List the guides."""
            time.sleep(self.listing_delay_seconds)
            assert include_header, "the listing is only useful with its headers"
            return LISTING

        @mcp.tool(name="load_datadog_skill")
        def load(
            skill_name: str,
            telemetry: dict[str, str],
            resource_path: str | None = None,
        ) -> str:
            """Load one guide, or one of its references."""
            self.loads.append((skill_name, resource_path))
            if self.refusals.get(skill_name, 0) > 0:
                self.refusals[skill_name] -= 1
                raise ValueError("Burst rate limit exceeded. Please slow down.")
            if resource_path is None:
                return TEXTS[skill_name]
            return REFERENCES[(skill_name, resource_path)]

        return mcp


@pytest.fixture
def platform() -> _Platform:
    return _Platform()


@pytest.fixture
def serve(free_port: int, platform: _Platform) -> Iterator[str]:
    """The fake platform over a real socket, for the length of one test."""
    server = uvicorn.Server(
        uvicorn.Config(
            platform.server().streamable_http_app(),
            host="127.0.0.1",
            port=free_port,
            log_level="error",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        if not thread.is_alive():
            pytest.fail("the fake MCP server did not start")
        time.sleep(0.01)
    yield f"http://127.0.0.1:{free_port}/mcp"
    server.should_exit = True
    thread.join(timeout=10)


def _deployment(endpoint: str, timeout_seconds: int = 30) -> Deployment:
    return Deployment(
        platforms={DATADOG: PlatformAccess(endpoint=endpoint, headers={})},
        model_for=lambda _: "unused",
        breakers=CircuitBreakers(mcp_call_timeout_seconds=timeout_seconds),
    )


async def _no_pause(_: float) -> None:
    return None


def test_a_guide_offered_to_the_crew_is_read_with_its_description_and_references(
    serve: str,
) -> None:
    guides = fetch_guides((LOGS,), _deployment(serve), pause=_no_pause)

    assert guides == (
        DatadogGuide(
            name="datadog/logs",
            description="Load this skill when searching logs.",
            text=TEXTS["datadog/logs"],
            references={"references/log-syntax.md": "Quote a value with spaces."},
        ),
    )


def test_a_guide_offered_to_nobody_has_no_reference_loaded(
    serve: str, platform: _Platform
) -> None:
    fetch_guides((LOGS,), _deployment(serve), pause=_no_pause)

    assert ("datadog/metrics", "references/metric-syntax.md") not in platform.loads


def test_a_refused_load_is_asked_again_after_a_pause(
    serve: str, platform: _Platform
) -> None:
    paused: list[float] = []

    async def pause(seconds: float) -> None:
        paused.append(seconds)

    platform.refusals["datadog/logs"] = 2

    guides = fetch_guides((LOGS,), _deployment(serve), pause=pause)

    assert [guide.name for guide in guides] == ["datadog/logs"]
    assert len(paused) == 2


def test_a_guide_the_platform_keeps_refusing_is_left_out_and_named(
    serve: str, platform: _Platform, caplog: pytest.LogCaptureFixture
) -> None:
    platform.refusals["datadog/logs"] = 1_000

    with caplog.at_level(logging.WARNING):
        guides = fetch_guides((LOGS,), _deployment(serve), pause=_no_pause)

    assert guides == ()
    assert "datadog/logs" in caplog.text


def test_an_unreachable_platform_offers_no_guides_and_says_so_once(
    free_port: int, caplog: pytest.LogCaptureFixture
) -> None:
    unreachable = f"http://127.0.0.1:{free_port}/mcp"

    guides_module = fetch_guides.__module__

    with caplog.at_level(logging.WARNING):
        guides = fetch_guides((LOGS,), _deployment(unreachable, 2), pause=_no_pause)

    assert guides == ()
    ours = [record for record in caplog.records if record.name == guides_module]
    assert [record.levelno for record in ours] == [logging.WARNING]


def test_a_platform_slower_than_the_call_bound_offers_no_guides(
    serve: str, platform: _Platform
) -> None:
    """Waiting on the platform is bounded; letting go of the session costs a little."""
    platform.listing_delay_seconds = 6.0
    started = time.monotonic()

    guides = fetch_guides((LOGS,), _deployment(serve, 1), pause=_no_pause)

    assert guides == ()
    assert time.monotonic() - started < 4.0


def test_a_crew_reaching_no_datadog_toolset_asks_the_platform_nothing(
    serve: str, platform: _Platform
) -> None:
    elsewhere = Specialist(
        name="elsewhere",
        signal=Signal.LOGS,
        instruction="Search elsewhere.",
        output_schema=_Report,
        toolsets=(Toolset("other", "core", ("search_logs",)),),
    )
    assert fetch_guides((elsewhere,), _deployment(serve), pause=_no_pause) == ()
    assert platform.loads == []
