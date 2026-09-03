"""Where Datadog's MCP server is, and what authenticates against it.

Everything else this module used to do — a port implementation and the
JSON-to-JSON translation behind it — is gone. A specialist reaches the
platform's toolset directly through ADK now, so what a deployment needs from
this file is an address and two headers.

It takes a site and two keys rather than the connection the Events API adapter
resolves: investigation has no business knowing that type. The composition root
resolves the connection once and hands the strings across, which is what keeps
the guarantee that a deployment able to fetch alerts is able to investigate
them without either side importing the other.
"""

DATADOG = "datadog"
"""What a declaration names to say that Datadog serves one of its toolsets.

A constant here rather than an enum in the domain. An enum would put every
provider's name in one closed list the domain owns, so adding a provider would
mean editing the core to say it exists — the opposite of what naming providers
per toolset is for. A constant beside the plumbing that resolves it keeps a
typo out of a declaration without making the domain the registry.
"""

API_KEY_HEADER = "DD_API_KEY"
APP_KEY_HEADER = "DD_APPLICATION_KEY"
"""What the MCP server calls the application key.

Deliberately not ``DD_APP_KEY``: that is the environment variable an operator
sets, and this is the header the server reads. They differ, and conflating
them fails as an authentication error that says nothing about which of the two
was wrong.
"""


def mcp_endpoint(site: str) -> str:
    """The MCP server's address for the account this deployment points at.

    Without the toolsets a caller wants: each specialist asks for its own,
    which is what keeps what one may reach in its declaration rather than
    here.

    Args:
        site: Datadog regional site, e.g. ``datadoghq.eu``.

    Returns:
        The MCP server's address for that site.
    """
    return f"https://mcp.{site}/v1/mcp"


def mcp_headers(*, api_key: str, app_key: str) -> dict[str, str]:
    """The credentials the MCP server authenticates a request with.

    Args:
        api_key: Datadog API key.
        app_key: Datadog application key.

    Returns:
        The headers to send, under the names the server reads them by.
    """
    return {
        API_KEY_HEADER: api_key,
        APP_KEY_HEADER: app_key,
    }
