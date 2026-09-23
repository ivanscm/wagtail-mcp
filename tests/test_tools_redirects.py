import itertools

import pytest

from test_protocol import TOOLS_LIST, call_tool, call_tool_raw, post
from wagtail.models import Locale, Page, Site

from wagtail_mcp.test.models import ContentPage


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def wagtail_baseline():
    """Ensure a default Locale + root page exist (see test_tools_pages_read)."""
    Locale.objects.get_or_create(language_code="en")
    if not Page.objects.filter(depth=1).exists():
        Page.objects.create(path="0001", depth=1, url_path="/", title="Root")
    yield


_counter = itertools.count()


@pytest.fixture
def target_page(wagtail_baseline):
    """A published ContentPage to redirect to, on its own site."""
    root = Page.objects.get(depth=1)
    page = ContentPage(title="Redirect Target", slug="redirect-target")
    root.add_child(instance=page)
    page.save_revision().publish()
    return page


@pytest.fixture
def created_redirect(client, token, target_page):
    """A redirect from /old/ to the target page, created through the tool."""
    return call_tool(
        client,
        token,
        "redirects_create",
        old_path="/old-gone",
        redirect_page_id=target_page.pk,
    )


def test_redirect_tools_annotations(client, token):

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    for name in ("redirects_list", "redirects_find", "redirects_detail"):
        assert tools[name].get("readOnlyHint") is True
    assert tools["redirects_create"].get("readOnlyHint") is not True
    assert tools["redirects_update"].get("readOnlyHint") is not True
    assert tools["redirects_delete"].get("destructiveHint") is True
    assert tools["redirects_list"].get("destructiveHint") is not True


def test_redirects_list_empty(client, token):
    result = call_tool(client, token, "redirects_list", limit=20, offset=0)
    assert result["count"] == 0
    assert result["items"] == []


def test_redirects_create_detail_find(client, token, target_page, created_redirect):
    created = created_redirect
    assert created["old_path"] == "/old-gone"
    assert created["redirect_page_id"] == target_page.pk
    assert created["is_permanent"] is True

    detail = call_tool(client, token, "redirects_detail", redirect_id=created["id"])
    assert detail["id"] == created["id"]
    assert detail["redirect_page_id"] == target_page.pk

    found = call_tool(client, token, "redirects_find", old_path="/old-gone")
    assert found["id"] == created["id"]


def test_redirects_list_includes_created(client, token, created_redirect):
    result = call_tool(client, token, "redirects_list", limit=20)
    paths = [item["old_path"] for item in result["items"]]
    assert "/old-gone" in paths
    assert result["count"] >= 1


def test_redirects_update(client, token, created_redirect, target_page):
    updated = call_tool(
        client,
        token,
        "redirects_update",
        redirect_id=created_redirect["id"],
        old_path="/moved",
    )
    assert updated["old_path"] == "/moved"
    detail = call_tool(
        client, token, "redirects_detail", redirect_id=created_redirect["id"]
    )
    assert detail["old_path"] == "/moved"


def test_redirects_update_preserves_page_target(
    client, token, created_redirect, target_page
):
    # Patching only `is_permanent` must NOT clear the existing link/page
    # target — the fetched current redirect is merged, so redirect_page_id
    # stays set (a regression guard against clobbering the target).
    updated = call_tool(
        client,
        token,
        "redirects_update",
        redirect_id=created_redirect["id"],
        is_permanent=False,
    )
    assert updated["is_permanent"] is False
    assert updated["redirect_page_id"] == target_page.pk

    detail = call_tool(
        client, token, "redirects_detail", redirect_id=created_redirect["id"]
    )
    assert detail["redirect_page_id"] == target_page.pk


def test_redirects_update_switch_target_to_link(client, token, created_redirect):
    # Providing an external link switches the target type: the page target is
    # cleared and the link set (redirects can target one OR the other).
    updated = call_tool(
        client,
        token,
        "redirects_update",
        redirect_id=created_redirect["id"],
        redirect_link="https://example.com/new",
    )
    assert updated["redirect_link"] == "https://example.com/new"
    assert updated["redirect_page_id"] is None


def test_redirects_delete(client, token, created_redirect):
    result = call_tool(
        client, token, "redirects_delete", redirect_id=created_redirect["id"]
    )
    assert result["deleted"] is True
    raw = call_tool_raw(
        client, token, "redirects_detail", redirect_id=created_redirect["id"]
    )
    assert raw["isError"] is True


def test_redirects_find_missing_is_error(client, token):
    raw = call_tool_raw(client, token, "redirects_find", old_path="/no-such-page/")
    assert raw["isError"] is True
    assert (
        "404" in raw["content"][0]["text"] or "Not Found" in raw["content"][0]["text"]
    )


def test_redirects_create_with_link_and_site(client, token, wagtail_baseline):
    # Cover the `redirect_link` + `site_id` create branches (link target + site
    # scope, vs the page-target / all-sites branches exercised elsewhere).
    root = Page.objects.get(depth=1)
    site = Site.objects.create(
        hostname="redirects-site.test", root_page=root, is_default_site=True
    )
    created = call_tool(
        client,
        token,
        "redirects_create",
        old_path="/old-link",
        redirect_link="https://example.com/dest",
        site_id=site.pk,
    )
    assert created["redirect_link"] == "https://example.com/dest"
    assert created["site_id"] == site.pk

    detail = call_tool(client, token, "redirects_detail", redirect_id=created["id"])
    assert detail["redirect_link"] == "https://example.com/dest"
    assert detail["site_id"] == site.pk


def test_redirects_update_sets_site_scope(
    client, token, created_redirect, wagtail_baseline
):
    # Pass an explicit `site_id` (the `update_body["site"] = site_id` branch).
    root = Page.objects.get(depth=1)
    site = Site.objects.create(
        hostname="redirects-update-site.test", root_page=root, is_default_site=True
    )
    updated = call_tool(
        client,
        token,
        "redirects_update",
        redirect_id=created_redirect["id"],
        site_id=site.pk,
    )
    assert updated["site_id"] == site.pk
    assert updated["redirect_page_id"] is not None  # target preserved


def test_redirects_update_switch_to_page_target(client, token, target_page):
    # Start from a link-target redirect, then switch it to a page target — the
    # `redirect_page_id is not None` + clear-link branch.
    created = call_tool(
        client,
        token,
        "redirects_create",
        old_path="/old-switch",
        redirect_link="https://example.com/start",
    )
    updated = call_tool(
        client,
        token,
        "redirects_update",
        redirect_id=created["id"],
        redirect_page_id=target_page.pk,
    )
    assert updated["redirect_page_id"] == target_page.pk
    assert updated["redirect_link"] in ("", None)
