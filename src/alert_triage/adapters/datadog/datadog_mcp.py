"""Where Datadog's MCP server is, and what authenticates against it.

Everything else this module used to do — a port implementation and the
JSON-to-JSON translation behind it — is gone. A specialist reaches the
platform's toolset directly through ADK now, so what a deployment needs from
this file is an address and two headers.

Both come from the same ``DatadogConnection`` the Events API adapter already
resolves: this adapter adds no environment variable of its own, and a
deployment that could fetch alerts can investigate them.
"""

from alert_triage.adapters.datadog.connection import DatadogConnection

API_KEY_HEADER = "DD_API_KEY"
APP_KEY_HEADER = "DD_APPLICATION_KEY"
"""What the MCP server calls the application key.

Deliberately not ``DD_APP_KEY``: that is the environment variable an operator
sets, and this is the header the server reads. They differ, and conflating
them fails as an authentication error that says nothing about which of the two
was wrong.
"""


def mcp_endpoint(connection: DatadogConnection) -> str:
    """The MCP server's address for the account this deployment points at.

    Without the toolsets a caller wants: each specialist asks for its own,
    which is what keeps what one may reach in its declaration rather than
    here.
    """
    return f"https://mcp.{connection.site}/v1/mcp"


def mcp_headers(connection: DatadogConnection) -> dict[str, str]:
    """The credentials the MCP server authenticates a request with."""
    return {
        API_KEY_HEADER: connection.api_key,
        APP_KEY_HEADER: connection.app_key,
    }
