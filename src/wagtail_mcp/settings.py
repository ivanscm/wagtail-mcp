from django.conf import settings


DEFAULTS = {
    "require_auth": True,
    # See docs/admin-agent.md for model and provider configuration.
    "agent_model": "",
    "agent_api_key": "",
    "agent_base_url": "",
}


def get_config() -> dict:
    """Return the wagtail_mcp settings, merging project overrides onto defaults.

    A project may provide a partial ``WAGTAIL_MCP`` dict; unspecified options
    fall back to ``DEFAULTS``.
    """
    return {**DEFAULTS, **getattr(settings, "WAGTAIL_MCP", {})}


def get_agent_config() -> dict:
    """Return the admin agent's model config."""
    config = get_config()
    return {
        "model": config["agent_model"],
        "api_key": config["agent_api_key"],
        "base_url": config["agent_base_url"],
    }
