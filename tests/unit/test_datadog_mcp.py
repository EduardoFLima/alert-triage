from alert_triage.investigation.adapters.datadog.mcp import (
    API_KEY_HEADER,
    APP_KEY_HEADER,
    mcp_endpoint,
    mcp_headers,
)


def test_the_endpoint_is_derived_from_the_default_site() -> None:
    assert mcp_endpoint("datadoghq.com") == "https://mcp.datadoghq.com/v1/mcp"


def test_the_endpoint_follows_a_non_default_site() -> None:
    """A region is a deployment fact; pointing at another one changes no code."""
    assert mcp_endpoint("datadoghq.eu") == "https://mcp.datadoghq.eu/v1/mcp"


def test_the_endpoint_asks_for_no_toolset_of_its_own() -> None:
    """What a specialist may reach is its declaration's business, not this one's."""
    assert "toolsets" not in mcp_endpoint("datadoghq.com")


def test_the_headers_are_the_ones_the_server_expects() -> None:
    """The server's header is DD_APPLICATION_KEY; our variable is DD_APP_KEY."""
    headers = mcp_headers(api_key="api", app_key="app")

    assert headers[API_KEY_HEADER] == "api"
    assert headers[APP_KEY_HEADER] == "app"
    assert APP_KEY_HEADER == "DD_APPLICATION_KEY"
