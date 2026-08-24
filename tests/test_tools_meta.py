"""Tool-layer tests for the meta tools: whoami, schema_list, schema_detail,
api_schema, and the api_call escape hatch.

These drive the whole stack through the /mcp/ endpoint (real MCP JSON-RPC),
so they exercise dispatch, auth forwarding, tool registration, and the SDK's
result serialization together.
"""

import pytest

from test_protocol import call_tool, call_tool_raw


@pytest.mark.django_db(transaction=True)
def test_whoami_returns_authenticated_user(client, token):
    # whoami resolves only the bearer token user (v3 auth); the shape is the
    # nested WhoAmISchema (user/profile/groups), not a flat structure.
    result = call_tool(client, token, "whoami")
    assert result["user"]["username"] == "admin"
    assert result["user"]["is_superuser"] is True
    assert "profile" in result
    assert "groups" in result


@pytest.mark.django_db(transaction=True)
def test_schema_list_lists_content_types(client, token):
    # schema_list returns {"types": [{name, label}, ...]}; assert our models.
    result = call_tool(client, token, "schema_list")
    names = {item["name"] for item in result["types"]}
    assert "wagtail_mcp_test.ContentPage" in names
    assert "wagtail_mcp_test.Person" in names


@pytest.mark.django_db(transaction=True)
def test_schema_detail_for_content_page(client, token):
    # The per-type schema is auto-generated; it has read/create/patch shapes.
    result = call_tool(
        client, token, "schema_detail", type_name="wagtail_mcp_test.ContentPage"
    )
    assert set(result) == {"read", "create", "patch"}
    assert "title" in result["create"]


@pytest.mark.django_db
def test_api_schema_full_document(client, token):
    result = call_tool(client, token, "api_schema")
    assert "paths" in result
    assert "components" in result
    assert len(result["paths"]) > 0


@pytest.mark.django_db
def test_api_schema_component_slice(client, token):
    # The page create schema is project-specific and auto-generated; grab a
    # slice of it by component name to prove the slice path works.
    result = call_tool(client, token, "api_schema", component="ContentPageCreateSchema")
    assert isinstance(result, dict)


@pytest.mark.django_db
def test_api_schema_unknown_component_is_error(client, token):
    result = call_tool_raw(
        client, token, "api_schema", component="DefinitelyNotAComponent"
    )
    assert result.get("isError") is True
    assert "DefinitelyNotAComponent" in result["content"][0]["text"]


@pytest.mark.django_db(transaction=True)
def test_api_call_escape_hatch(client, token):
    # locales_list is a real read-only operation, mounted once wagtail.locales
    # is in INSTALLED_APPS (regression-pinned in test_dispatch).
    result = call_tool(client, token, "api_call", operation_id="locales_list")
    assert result["count"] >= 0


@pytest.mark.django_db
def test_api_call_unknown_operation(client, token):
    result = call_tool_raw(client, token, "api_call", operation_id="nope")
    assert result.get("isError") is True
    assert "Unknown operation" in result["content"][0]["text"]


@pytest.mark.django_db
def test_tool_inventory_counts_meta_tools(client, token):
    # Confirm exactly the meta + page tools are registered (5 meta + 3 page
    # read + 4 page write tools + 10 page action tools; Task 14 adds the full
    # 57-tool inventory test).
    from test_protocol import post

    response = post(
        client, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, token
    )
    tools = response.json()["result"]["tools"]
    assert len(tools) == 22
