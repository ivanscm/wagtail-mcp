import itertools

import pytest

from test_protocol import TOOLS_LIST, call_tool, call_tool_raw, post
from wagtail.models import Locale, Page, Site


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def wagtail_baseline():
    """Ensure a default Locale + root page exist (see test_tools_pages_read)."""
    Locale.objects.get_or_create(language_code="en")
    if not Page.objects.filter(depth=1).exists():
        Page.objects.create(path="0001", depth=1, url_path="/", title="Root")
    root = Page.objects.get(depth=1)
    if not Site.objects.filter(hostname="testserver").exists():
        Site.objects.create(hostname="testserver", root_page=root, is_default_site=True)
    yield


_counter = itertools.count()


@pytest.fixture
def root_page_id(wagtail_baseline):
    return Page.objects.get(depth=1).pk


def test_site_tools_annotations(client, token):

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    for name in ("sites_list", "sites_detail"):
        assert tools[name].get("readOnlyHint") is True
    assert tools["sites_create"].get("readOnlyHint") is not True
    assert tools["sites_update"].get("readOnlyHint") is not True
    assert tools["sites_delete"].get("destructiveHint") is True


def test_sites_list_has_baseline(client, token):
    result = call_tool(client, token, "sites_list", limit=20, offset=0)
    hostnames = [item["hostname"] for item in result["items"]]
    assert "testserver" in hostnames
    assert result["count"] >= 1


def test_sites_create_detail(client, token, root_page_id):
    created = call_tool(
        client,
        token,
        "sites_create",
        hostname=f"site-{next(_counter)}.test",
        root_page_id=root_page_id,
        site_name="Created Site",
        port=8080,
    )
    assert created["hostname"].startswith("site-")
    assert created["site_name"] == "Created Site"
    assert created["port"] == 8080
    assert created["root_page_id"] == root_page_id
    assert created["is_default_site"] is False

    detail = call_tool(client, token, "sites_detail", site_id=created["id"])
    assert detail["id"] == created["id"]
    assert detail["site_name"] == "Created Site"


def test_sites_update(client, token, root_page_id):
    created = call_tool(
        client,
        token,
        "sites_create",
        hostname=f"site-{next(_counter)}.test",
        root_page_id=root_page_id,
    )
    updated = call_tool(
        client,
        token,
        "sites_update",
        site_id=created["id"],
        site_name="Renamed",
    )
    assert updated["site_name"] == "Renamed"
    assert updated["hostname"] == created["hostname"]  # untouched field preserved


def test_sites_delete(client, token, root_page_id):
    created = call_tool(
        client,
        token,
        "sites_create",
        hostname=f"site-{next(_counter)}.test",
        root_page_id=root_page_id,
    )
    result = call_tool(client, token, "sites_delete", site_id=created["id"])
    assert result["deleted"] is True
    assert not Site.objects.filter(pk=created["id"]).exists()


def test_sites_detail_missing_is_error(client, token):
    raw = call_tool_raw(client, token, "sites_detail", site_id=999999)
    assert raw["isError"] is True
