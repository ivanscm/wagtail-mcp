"""Inventory check: the exact curated tool surface, and that every tool carries
MCP annotations (so clients get correct read-only/destructive/idempotent UX).

This pins the full 60-tool surface delivered over the plan's tool tasks.
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
