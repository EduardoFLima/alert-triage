"""Reaching Datadog's MCP server, and reading what it says back.

Where the server is and how to authenticate come from the same
``DatadogConnection`` the Events API adapter already resolves: this adapter
adds no environment variable of its own, and a deployment that could fetch
alerts can investigate them.

What crosses back is translated into ``LogRecord`` here and nowhere else,
which is what keeps the Logs agent — and everything above it — free of
Datadog's field names.
"""

import asyncio
import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from alert_triage.adapters.datadog.connection import DatadogConnection
from alert_triage.domain.findings import LogRecord
from alert_triage.domain.window import Window
from alert_triage.ports.observability_platform import ObservabilityPlatformError

LOGS_TOOLSET = "core"
"""The one toolset holding the log search this port needs.

Asked for by name rather than taking the server's default, so widening what an
agent can reach stays a deliberate edit here.
"""

API_KEY_HEADER = "DD_API_KEY"
APP_KEY_HEADER = "DD_APPLICATION_KEY"
"""What the MCP server calls the application key.

Deliberately not ``DD_APP_KEY``: that is the environment variable an operator
sets, and this is the header the server reads. They differ, and conflating
them fails as an authentication error that says nothing about which of the two
was wrong.
"""


def mcp_endpoint(connection: DatadogConnection) -> str:
    """The MCP server's URL for the account this deployment points at."""
    return f"https://mcp.{connection.site}/v1/mcp?toolsets={LOGS_TOOLSET}"


def mcp_headers(connection: DatadogConnection) -> dict[str, str]:
    """The credentials the MCP server authenticates a request with."""
    return {
        API_KEY_HEADER: connection.api_key,
        APP_KEY_HEADER: connection.app_key,
    }


def records_from(payloads: Iterable[Any]) -> tuple[LogRecord, ...]:
    """Translate what the log search returned into domain records.

    A payload that cannot be read is an error rather than a record quietly
    dropped: a partial answer presented as a whole one would let an
    investigation conclude a service was quiet on the strength of a parsing
    failure.

    Args:
        payloads: The log entries the platform returned, in its own shape.

    Returns:
        The records, in the order they arrived.

    Raises:
        ObservabilityPlatformError: An entry could not be read as a log record.
    """
    return tuple(_record(payload) for payload in payloads)


def _record(payload: Any) -> LogRecord:
    """Read one log entry, insisting on what makes it recognisable to a human."""
    if not isinstance(payload, dict):
        raise ObservabilityPlatformError(
            f"Expected a log record from the platform, got {type(payload).__name__}"
        )
    try:
        return LogRecord(
            timestamp=_instant(payload.get("timestamp")),
            level=_text(payload, "status"),
            message=_text(payload, "message"),
            service=_text(payload, "service"),
        )
    except ValueError as error:
        raise ObservabilityPlatformError(
            f"The platform returned a log record that could not be read: {error}"
        ) from error


def _text(payload: dict[str, Any], key: str) -> str:
    """Read a field a record cannot do without."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or empty '{key}'")
    return value


def _instant(raw: Any) -> datetime:
    """Read the instant a line was logged, however the platform spelled it."""
    if not isinstance(raw, str):
        raise ValueError("missing 'timestamp'")
    try:
        return datetime.fromisoformat(raw)
    except ValueError as error:
        raise ValueError(f"unreadable 'timestamp' {raw!r}") from error


LOG_SEARCH_TOOL = "search_datadog_logs"
"""The MCP tool behind ``search_logs``.

Named here and nowhere else. It is the one Datadog-specific string in the
investigation path, and keeping it inside the adapter is what lets a second
platform satisfy the same port without an agent noticing.
"""


class DatadogMcpPlatform:
    """The ObservabilityPlatform port, answered over Datadog's MCP server.

    MCP is the transport, not the interface an agent sees: the agent is given
    this project's ``search_logs``, and which tool on which server answers it
    stops here.

    The MCP client is asynchronous; the event loop is owned inside each call,
    so the port stays synchronous like every other adapter in the project.
    """

    def __init__(
        self, connection: DatadogConnection, *, timeout_seconds: int = 30
    ) -> None:
        """Point the platform at one Datadog account.

        Args:
            connection: Where Datadog is and how to authenticate.
            timeout_seconds: Bound on a single call to the server.
        """
        self._endpoint = mcp_endpoint(connection)
        self._headers = mcp_headers(connection)
        self._timeout_seconds = timeout_seconds

    def search_logs(
        self, service: str, window: Window, query: str
    ) -> Sequence[LogRecord]:
        """Search a service's logs over a window.

        Args:
            service: Service tag whose logs are wanted.
            window: The period to search over.
            query: What to look for, in the caller's own terms.

        Returns:
            The matching records, in the order the platform returned them.

        Raises:
            ObservabilityPlatformError: The search could not be performed, or
                what came back could not be read as log records.
        """
        try:
            payloads = asyncio.run(self._call(service, window, query))
        except ObservabilityPlatformError:
            raise
        except Exception as error:
            raise ObservabilityPlatformError(
                f"Searching {service} logs failed: {error}"
            ) from error
        return records_from(payloads)

    async def _call(self, service: str, window: Window, query: str) -> Iterable[Any]:
        """Open a session, call the log search once, and read what came back."""
        from mcp import ClientSession
        from mcp.client.streamable_http import (
            create_mcp_http_client,
            streamable_http_client,
        )

        client = create_mcp_http_client(headers=self._headers)
        async with (
            client,
            streamable_http_client(self._endpoint, http_client=client) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                LOG_SEARCH_TOOL,
                {
                    "query": f"service:{service} {query}".strip(),
                    "from": window.start.isoformat(),
                    "to": window.end.isoformat(),
                },
                read_timeout_seconds=self._timeout_seconds,
            )
        return _entries(result)


def _entries(result: Any) -> Iterable[Any]:
    """Read the log entries out of an MCP tool result.

    A server may answer structurally or as a block of JSON text; both are read
    here, so the shape of the answer stays the adapter's problem rather than
    anybody else's.
    """
    if getattr(result, "isError", False):
        raise ObservabilityPlatformError(
            f"The platform refused the log search: {_text_of(result)}"
        )
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        found = _listed(structured)
        if found is not None:
            return found
    text = _text_of(result)
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise ObservabilityPlatformError(
            f"The platform's answer could not be read: {error}"
        ) from error
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return _listed(parsed) or ()
    return ()


def _listed(payload: dict[str, Any]) -> list[Any] | None:
    """Find the list of entries a server wrapped in an envelope."""
    for key in ("logs", "data", "results"):
        found = payload.get(key)
        if isinstance(found, list):
            return found
    return None


def _text_of(result: Any) -> str:
    """Join whatever text a tool result carries."""
    return "".join(
        getattr(block, "text", "") or ""
        for block in (getattr(result, "content", None) or ())
    )
