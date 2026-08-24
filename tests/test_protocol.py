import json

import pytest


INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

ACCEPT = "application/json, text/event-stream"


def post(client, payload, token=None):
    headers = {"content_type": "application/json", "HTTP_ACCEPT": ACCEPT}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.post("/mcp/", json.dumps(payload), **headers)


def tools_call_payload(name, arguments=None, request_id=3):
    """Build a JSON-RPC ``tools/call`` payload for a tool call."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }


def call_tool(client, token, name, request_id=10, **arguments):
    """Call a tool over the /mcp/ endpoint and return its parsed result.

    Prefers ``structuredContent`` when the SDK returns it (dict-returning tools
    do); otherwise parses the single text content block as JSON.
    """
    result = call_tool_raw(client, token, name, request_id=request_id, **arguments)
    assert result.get("isError") is False, result
    if "structuredContent" in result:
        return result["structuredContent"]
    text = result["content"][0]["text"]
    return json.loads(text) if text else None


def call_tool_raw(client, token, name, request_id=10, **arguments):
    """Call a tool over the /mcp/ endpoint and return the full CallToolResult dict."""
    response = post(client, tools_call_payload(name, arguments, request_id), token)
    assert response.status_code == 200, response.content
    return response.json()["result"]


@pytest.mark.django_db
def test_initialize_and_tools_list(client, token):
    response = post(client, INIT, token)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["serverInfo"]["name"] == "wagtail-mcp"
    response = post(client, TOOLS_LIST, token)
    tools = response.json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {
        "whoami",
        "schema_list",
        "schema_detail",
        "api_schema",
        "api_call",
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
        "images_list",
        "images_detail",
        "images_create",
        "images_update",
        "images_delete",
        "documents_list",
        "documents_detail",
        "documents_create",
        "documents_update",
        "documents_delete",
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
    }


@pytest.mark.django_db
def test_post_without_token_is_401(client):
    response = post(client, INIT)
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"


@pytest.mark.django_db
def test_get_is_405(client, token):
    response = client.get(
        "/mcp/", HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ACCEPT=ACCEPT
    )
    assert response.status_code == 405


@pytest.mark.django_db
def test_require_auth_false_allows_anonymous(client, settings):
    settings.WAGTAIL_MCP = {"require_auth": False}
    response = post(client, INIT)
    assert response.status_code == 200


@pytest.mark.django_db
def test_malformed_jsonrpc(client, settings, token):
    settings.WAGTAIL_MCP = {"require_auth": True}
    response = post(client, {"jsonrpc": "2.0", "id": 9, "method": "no/such"}, token)
    body = response.json()
    assert "error" in body
