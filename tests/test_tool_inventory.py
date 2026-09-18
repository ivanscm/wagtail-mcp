"""Inventory check: the exact curated tool surface, and that every tool carries
MCP annotations (so clients get correct read-only/destructive/idempotent UX).

This pins the full 60-tool surface delivered over the plan's tool tasks, plus
the pagination limit stated in paginated tool descriptions.
"""

import pytest

from test_protocol import TOOLS_LIST, post


#: Full 60-tool inventory, grouped by source module / v3 operation prefix.
EXPECTED_TOOLS = {
    # meta — 5 (4 operation-aligned + api_call + api_schema net-new)
    "whoami",
    "schema_list",
    "schema_detail",
    "api_schema",
    "api_call",
    # pages — 17
    "pages_list",
    "pages_find",
    "pages_detail",
    "pages_create",
    "pages_update",
    "pages_delete",
    "pages_actions_delete",
    "pages_actions_publish",
    "pages_actions_unpublish",
    "pages_actions_copy",
    "pages_actions_move",
    "pages_actions_revert",
    "pages_actions_convert_alias",
    "pages_actions_create_alias",
    "pages_actions_copy_for_translation",
    "pages_revisions_list",
    "pages_revisions_detail",
    # images — 5
    "images_list",
    "images_detail",
    "images_create",
    "images_update",
    "images_delete",
    # documents — 5
    "documents_list",
    "documents_detail",
    "documents_create",
    "documents_update",
    "documents_delete",
    # snippets — 12
    "snippets_list",
    "snippets_detail",
    "snippets_create",
    "snippets_update",
    "snippets_delete",
    "snippets_actions_delete",
    "snippets_revisions_list",
    "snippets_revisions_detail",
    "snippets_actions_publish",
    "snippets_actions_unpublish",
    "snippets_actions_revert",
    "snippets_actions_copy_for_translation",
    # redirects — 6
    "redirects_list",
    "redirects_find",
    "redirects_detail",
    "redirects_create",
    "redirects_update",
    "redirects_delete",
    # sites — 5
    "sites_list",
    "sites_detail",
    "sites_create",
    "sites_update",
    "sites_delete",
    # locales — 5
    "locales_list",
    "locales_detail",
    "locales_create",
    "locales_update",
    "locales_delete",
}

#: Every hint must be explicitly set (not None) so clients render correct UX.
ANNOTATION_HINTS = (
    "readOnlyHint",
    "destructiveHint",
    "idempotentHint",
    "openWorldHint",
)

#: Tools taking ``limit``/``offset``; their descriptions must state the cap.
PAGINATED_TOOLS = (
    "pages_list",
    "pages_revisions_list",
    "images_list",
    "documents_list",
    "snippets_list",
    "snippets_revisions_list",
    "redirects_list",
    "sites_list",
    "locales_list",
)


@pytest.mark.django_db
def test_exact_tool_inventory(client, token):
    """tools/list reports exactly the curated 60 tools, all annotated."""
    response = post(client, TOOLS_LIST, token)
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == EXPECTED_TOOLS, _inventory_diff(names)

    # Every tool declares every annotation hint (explicitly set, not None).
    for tool in tools:
        annotations = tool.get("annotations", {})
        missing = [hint for hint in ANNOTATION_HINTS if hint not in annotations]
        assert not missing, f"tool {tool['name']!r} missing annotation hints: {missing}"
        assert all(annotations[h] is not None for h in ANNOTATION_HINTS)


def _inventory_diff(actual):
    """Human-readable diff between expected and actual tool sets."""
    missing = EXPECTED_TOOLS - actual
    extra = actual - EXPECTED_TOOLS
    return f"\nmissing: {sorted(missing)}\nextra: {sorted(extra)}"


def _tools_by_name(client, token):
    response = post(client, TOOLS_LIST, token)
    assert response.status_code == 200
    return {tool["name"]: tool for tool in response.json()["result"]["tools"]}


@pytest.mark.django_db
def test_paginated_tool_descriptions_state_the_default_limit(client, token):
    """Every paginated tool's description states the v3 API's default cap.

    The v3 API 400s on ``limit`` above ``WAGTAILAPI_LIMIT_MAX`` (default 20);
    agents must learn the cap from the description, not from a failed call.
    """
    tools = _tools_by_name(client, token)
    for name in PAGINATED_TOOLS:
        assert (
            "Maximum `limit` is 20 (`WAGTAILAPI_LIMIT_MAX`)."
            in tools[name]["description"]
        ), f"tool {name!r} description does not state the default limit max"


@pytest.mark.django_db
def test_paginated_tool_descriptions_follow_the_site_limit_max_setting(
    client, token, settings
):
    """Descriptions are built at registration time from the site's setting.

    A project that lowers ``WAGTAILAPI_LIMIT_MAX`` gets its own cap baked into
    the tool descriptions, so agents never exceed it.
    """
    from wagtail_mcp.server import get_server

    settings.WAGTAILAPI_LIMIT_MAX = 5
    # Tool descriptions are frozen into the per-process server singleton;
    # clear the cache so registration re-reads the (overridden) setting.
    get_server.cache_clear()
    try:
        tools = _tools_by_name(client, token)
    finally:
        # Restore the default server for the remaining tests.
        get_server.cache_clear()
    for name in PAGINATED_TOOLS:
        assert (
            "Maximum `limit` is 5 (`WAGTAILAPI_LIMIT_MAX`)."
            in tools[name]["description"]
        ), f"tool {name!r} description does not state the site's limit max"


def test_max_limit_hint_without_cap(settings):
    """``WAGTAILAPI_LIMIT_MAX = None`` disables the cap; the hint says so."""
    from wagtail_mcp.tools.common import max_limit_hint

    settings.WAGTAILAPI_LIMIT_MAX = None
    assert max_limit_hint() == "`limit` has no maximum."
