import itertools

import pytest

from test_protocol import call_tool, call_tool_raw
from wagtail.models import Locale, Page, Site

from wagtail_mcp.test.models import ContentPage


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def wagtail_baseline():
    """Ensure a default Locale + root page exist.

    ``transaction=True`` truncates the DB between tests, wiping the
    migration-seeded Locale and root page, so each test reseeds them here.
    """
    Locale.objects.get_or_create(language_code="en")
    if not Page.objects.filter(depth=1).exists():
        Page.objects.create(path="0001", depth=1, url_path="/", title="Root")
    yield


_hostname_counter = itertools.count()


@pytest.fixture
def site_root(wagtail_baseline):
    """A deterministic site: root page, default site on unique hostname, one
    published ContentPage child."""
    root = Page.objects.get(depth=1)
    site_root = ContentPage(title="Site root", slug=f"root-{next(_hostname_counter)}")
    root.add_child(instance=site_root)
    hostname = f"site-{next(_hostname_counter)}.test"
    Site.objects.create(hostname=hostname, root_page=site_root, is_default_site=True)
    page = ContentPage(title="The Target", slug="the-target")
    site_root.add_child(instance=page)
    page.save_revision().publish()
    page.site_root = site_root  # expose for tests that need it
    return site_root


def test_page_tools_are_readonly(client, token):
    # Read tools must be advertised as readOnly (MCP annotation), which drives
    # safe client UX (no confirmation prompts). Checked over tools/list.
    from test_protocol import TOOLS_LIST, post

    response = post(client, TOOLS_LIST, token)
    tools = response.json()["result"]["tools"]
    page_tools = {t["name"]: t.get("annotations", {}) for t in tools}
    for name in ("pages_list", "pages_find", "pages_detail"):
        assert name in page_tools
        ann = page_tools[name]
        assert ann.get("readOnlyHint") is True
        assert ann.get("destructiveHint") is not True


def test_pages_list_returns_published_page(client, token, site_root):
    result = call_tool(client, token, "pages_list", limit=20, offset=0)
    assert result["count"] >= 1
    titles = [item["title"] for item in result["items"]]
    assert "The Target" in titles
    assert "next_offset" in result


def test_pages_list_child_of_filter(client, token, site_root):
    result = call_tool(client, token, "pages_list", child_of=site_root.pk, limit=20)
    ids = [item["id"] for item in result["items"]]
    assert ids == [site_root.get_children()[0].pk]
    assert result["count"] == 1


def test_pages_find_by_path(client, token, site_root):
    result = call_tool(client, token, "pages_find", html_path="the-target/")
    assert result["id"] == site_root.get_children()[0].pk


def test_pages_detail_live(client, token, site_root):
    target = site_root.get_children()[0]
    result = call_tool(client, token, "pages_detail", page_id=target.pk)
    assert result["id"] == target.pk
    assert result["title"] == "The Target"
    assert result["meta"]["slug"] == "the-target"


def test_pages_detail_keeps_empty_and_null_fields(client, token, site_root):
    """Detail responses pass through every field the API returned, including
    empty strings and nulls: an agent must be able to tell "field is empty"
    from "field not exposed" (regression: empty meta.seo_title and
    meta.search_description were silently dropped, so agents had to guess
    the SEO state and verify it against the rendered HTML)."""
    target = site_root.get_children()[0]
    result = call_tool(client, token, "pages_detail", page_id=target.pk)
    assert result["meta"]["seo_title"] == ""
    assert result["meta"]["search_description"] == ""
    assert result["meta"]["alias_of"] is None
    assert result["meta"]["detail_url"]


def test_pages_find_unknown_path_errors(client, token):
    raw = call_tool_raw(client, token, "pages_find", html_path="no-such-page/")
    assert raw["isError"] is True
    assert (
        "404" in raw["content"][0]["text"] or "Not Found" in raw["content"][0]["text"]
    )


def test_pages_detail_missing_errors(client, token):
    raw = call_tool_raw(client, token, "pages_detail", page_id=999999)
    assert raw["isError"] is True
