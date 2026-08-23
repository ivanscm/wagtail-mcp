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


@pytest.mark.django_db
def test_initialize_and_tools_list(client, token):
    response = post(client, INIT, token)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["serverInfo"]["name"] == "wagtail-mcp"
    response = post(client, TOOLS_LIST, token)
    assert response.json()["result"]["tools"] == []  # zero tools until Task 6


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
