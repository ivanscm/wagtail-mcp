"""Opt-in checks for the admin agent.

The agent is opt-in: a project enables it by mounting
``wagtail_mcp.agent.urls`` (AG-UI endpoint) from its root URLconf and
installing the ``wagtail-mcp[agent]`` extra. Everything the admin renders is
keyed on that mount: the URL namespace ``wagtail_mcp_agent`` only exists once
the include is in place. See docs/admin-agent.md.
"""

from django.urls import NoReverseMatch, reverse


def try_reverse_agent_endpoint() -> str | None:
    """The endpoint URL when mounted, else ``None`` (instead of raising)."""
    try:
        return reverse("wagtail_mcp_agent:endpoint")
    except NoReverseMatch:
        return None


__all__ = ["try_reverse_agent_endpoint"]
