from django.conf import settings


DEFAULTS = {"require_auth": True}


def get_config() -> dict:
    """Return the wagtail_mcp settings, merging project overrides onto defaults.

    A project may provide a partial ``WAGTAIL_MCP`` dict; unspecified options
    fall back to ``DEFAULTS``.
    """
    return {**DEFAULTS, **getattr(settings, "WAGTAIL_MCP", {})}
