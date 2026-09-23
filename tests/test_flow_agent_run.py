"""End-to-end agent run tests (transactional).

A real AG-UI run dispatches its tool calls through worker threads whose DB
connections cannot see a wrapping test transaction — so these tests are
``transaction=True`` (the same reason ``test_editorial_scenario`` is), with
the baseline data reseeded per test (the post-test flush wipes the
migration-seeded rows).

The module name sorts *after* ``test_editorial_scenario`` on purpose: the
post-test flush destroys migration-seeded rows (root page, default Site)
that earlier modules depend on, and editorial is the last such module.
"""

import json
import uuid

import pytest

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import _get_new_csrf_string
from wagtail.models import APIToken, Locale, Page, Site

from wagtail_mcp.agent import auth as agent_auth
from wagtail_mcp.agent import registry as agent_registry


pytestmark = pytest.mark.django_db(transaction=True)

ENDPOINT = "/admin/wagtail_mcp/agent/api/"


@pytest.fixture(autouse=True)
def _agent_baseline():
    """Reseed the rows the transactional teardown flush wipes (same pattern as
    test_editorial_scenario): the default Locale, the root page, and a default
    Site — the v3 API's ``child_of=root`` resolves through
    ``Site.find_for_request``, so a missing Site record breaks every later
    ``pages_list`` call with a None root_page."""

    Locale.objects.get_or_create(language_code="en")
    if not Page.objects.filter(depth=1).exists():
        Page.objects.create(path="0001", depth=1, url_path="/", title="Root")
    if not Site.objects.filter(is_default_site=True).exists():
        home = Page.objects.filter(depth=2).first()
        if home is None:
            home = Page.objects.create(
                path="00010001",
                depth=2,
                url_path="/home/",
                title="Welcome",
                slug="welcome",
            )
        Site.objects.create(hostname="localhost", root_page=home, is_default_site=True)
    yield


async def make_admin_async(client, username):

    return await sync_to_async(get_user_model().objects.create_superuser)(
        username, "a@example.com", "pw"
    )


def seed_csrf(client):
    """Seed a valid CSRF cookie on ``client`` and return the token to send."""

    token = _get_new_csrf_string()
    client.cookies[settings.CSRF_COOKIE_NAME] = token
    return token


async def parse_sse(response):
    """Drain a StreamingHttpResponse's SSE frames into event dicts."""
    chunks = []
    async for chunk in response.streaming_content:
        chunks.append(chunk)
    body = b"".join(chunks).decode()
    events = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if frame.startswith("data: "):
            events.append(json.loads(frame[len("data: ") :]))
    return events


async def test_run_streams_agui_events_with_a_tool_round(async_client):
    """With the default TestModel, a run streams AG-UI events end-to-end and
    actually calls a bridged tool as the logged-in admin user."""

    agent_registry.reset_cache()
    agent_auth.clear_cache()
    username = f"agentrun{uuid.uuid4().hex[:8]}"
    user = await make_admin_async(async_client, username)
    await async_client.aforce_login(user)

    token = seed_csrf(async_client)
    response = await async_client.post(
        ENDPOINT,
        data=json.dumps(
            {
                "threadId": "t-1",
                "runId": "r-1",
                "messages": [
                    {"id": "m-1", "role": "user", "content": "hello"},
                ],
                "tools": [],
                "state": {},
                "context": [],
                "forwardedProps": {},
            }
        ),
        content_type="application/json",
        HTTP_ACCEPT="text/event-stream",
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")

    events = await parse_sse(response)
    types = [event["type"] for event in events]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "RUN_ERROR" not in types
    # TestModel calls every registered tool; the tool result event carries
    # serialized content and the AG-UI camelCase field names that
    # @ag-ui/client 0.0.59 (pinned by @copilotkit/react-core) parses.
    result = next(e for e in events if e["type"] == "TOOL_CALL_RESULT")
    assert result["role"] == "tool"
    start = next(e for e in events if e["type"] == "TOOL_CALL_START")
    assert "toolCallName" in start
    assert "toolCallId" in start

    # The agent minted exactly one API token for the acting user.
    tokens = await sync_to_async(list)(
        APIToken.objects.filter(user=user, name=agent_auth.TOKEN_NAME)
    )
    assert len(tokens) == 1
