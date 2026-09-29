DATADOG = "datadog"
"""Names the provider without making the domain a provider registry."""

API_KEY_HEADER = "DD_API_KEY"
APP_KEY_HEADER = "DD_APPLICATION_KEY"
"""Datadog's server reads this header, not the operator's ``DD_APP_KEY`` name."""


def mcp_endpoint(site: str) -> str:
    return f"https://mcp.{site}/v1/mcp"


def mcp_headers(*, api_key: str, app_key: str) -> dict[str, str]:
    return {
        API_KEY_HEADER: api_key,
        APP_KEY_HEADER: app_key,
    }
