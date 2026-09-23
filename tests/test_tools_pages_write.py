import itertools

import pytest

from test_protocol import TOOLS_LIST, call_tool, call_tool_raw, post
from wagtail.models import Locale, Page

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
    """A deterministic published site root under which write tests create pages."""
    root = Page.objects.get(depth=1)
    site_root = ContentPage(title="Site root", slug=f"root-{next(_hostname_counter)}")
    root.add_child(instance=site_root)
    site_root.save_revision().publish()
    return site_root


def _created_page(result, wagtail_baseline):
    """Return the DB ContentPage instance created by ``result`` (by id)."""
    return ContentPage.objects.get(pk=result["id"])


def test_pages_create_makes_draft(client, token, site_root):
    result = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Created by API",
    )
    assert result["id"]
    assert result["title"] == "Created by API"
    assert result["meta"]["type"] == "wagtail_mcp_test.ContentPage"
    page = _created_page(result, site_root)
    assert page.get_parent().pk == site_root.pk
    assert page.live is False
    assert page.has_unpublished_changes is True


def test_pages_create_publish_true_publishes(client, token, site_root):
    result = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Published by API",
        publish=True,
    )
    page = _created_page(result, site_root)
    assert page.live is True
    assert page.has_unpublished_changes is False


def test_pages_create_markdown_body_converted_to_html(client, token, site_root):
    # Markdown input is sent as the {"format": "db_markdown", "content": ...}
    # envelope; the server stores the converted database HTML, and the read
    # path reports it back as Markdown.
    result = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Markdown body",
        body_markdown="# Hello\n\n**bold** text",
    )
    page = _created_page(result, site_root)
    # Markdown converts to database HTML server-side. `#` (h1) is not a
    # default rich-text feature so it's unwrapped to plain text; `**bold**`
    # becomes a `<b>` (the default bold feature), and Markdown syntax is gone.
    assert "<b>bold</b>" in page.body
    assert "**bold**" not in page.body
    # Read-back is Markdown again (rich_text_format defaults to markdown).
    detail = call_tool(client, token, "pages_detail", page_id=result["id"])
    assert "**bold**" in detail["body"]


def test_pages_create_bad_type_is_error(client, token, site_root):
    raw = call_tool_raw(
        client,
        token,
        "pages_create",
        type="no.such.Model",
        parent_id=site_root.pk,
        title="Nope",
    )
    assert raw["isError"] is True
    text = raw["content"][0]["text"]
    assert "422" in text
    assert "no.such.Model" in text


def test_pages_update_changes_fields(client, token, site_root):
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Before",
    )
    result = call_tool(
        client,
        token,
        "pages_update",
        page_id=created["id"],
        title="After",
        body_markdown="# Updated",
    )
    assert result["id"] == created["id"]
    assert result["title"] == "After"
    page = _created_page(result, site_root)
    assert page.title == "After"
    assert "<h2>Updated</h2>" in page.body or "Updated" in page.body


def test_pages_create_seo_fields(client, token, site_root):
    result = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="SEO page",
        slug="seo-page",
        seo_title="Better search title",
        search_description="A meta description for agents.",
        show_in_menus=True,
    )
    page = _created_page(result, site_root)
    assert page.slug == "seo-page"
    assert page.seo_title == "Better search title"
    assert page.search_description == "A meta description for agents."
    assert page.show_in_menus is True
    # The v3 read shape reports the SEO fields under `meta`; the detail tool
    # must surface them so agents can read back what they wrote.
    assert result["meta"]["seo_title"] == "Better search title"
    assert result["meta"]["search_description"] == "A meta description for agents."
    detail = call_tool(client, token, "pages_detail", page_id=result["id"])
    assert detail["meta"]["seo_title"] == "Better search title"
    assert detail["meta"]["search_description"] == "A meta description for agents."


def test_pages_update_seo_fields(client, token, site_root):
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="SEO draft",
        seo_title="Old title tag",
        search_description="Old description",
    )
    result = call_tool(
        client,
        token,
        "pages_update",
        page_id=created["id"],
        slug="new-slug",
        seo_title="New title tag",
        search_description="New description",
        show_in_menus=True,
    )
    page = _created_page(result, site_root)
    assert page.slug == "new-slug"
    assert page.seo_title == "New title tag"
    assert page.search_description == "New description"
    assert page.show_in_menus is True
    assert result["meta"]["seo_title"] == "New title tag"
    assert result["meta"]["search_description"] == "New description"


def test_pages_update_extra_fields(client, token, site_root):
    # `fields` covers writable fields the tool has no typed argument for,
    # including the raw db_html body workaround for image embeds.
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Raw html",
    )
    result = call_tool(
        client,
        token,
        "pages_update",
        page_id=created["id"],
        fields={"body": "<p>Raw <b>db_html</b> body</p>"},
    )
    page = _created_page(result, site_root)
    assert "Raw <b>db_html</b> body" in page.body


def test_pages_create_fields_typed_arguments_win(client, token, site_root):
    # A key passed both via `fields` and as a typed argument resolves to the
    # typed argument; `meta` in `fields` cannot clobber the envelope.
    result = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Clash",
        seo_title="Typed wins",
        fields={"seo_title": "Fields loses", "meta": {"type": "no.such.Model"}},
    )
    page = _created_page(result, site_root)
    assert page.seo_title == "Typed wins"
    assert result["meta"]["type"] == "wagtail_mcp_test.ContentPage"


def test_pages_update_publish_true_publishes(client, token, site_root):
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Draft for publish",
    )
    assert _created_page(created, site_root).live is False
    result = call_tool(
        client,
        token,
        "pages_update",
        page_id=created["id"],
        title="Now published",
        publish=True,
    )
    page = _created_page(result, site_root)
    assert page.live is True


def test_pages_delete_removes_page(client, token, site_root):
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="To delete",
    )
    result = call_tool(client, token, "pages_delete", page_id=created["id"])
    assert result["deleted"] is True
    assert not Page.objects.filter(pk=created["id"]).exists()


def test_pages_actions_delete_removes_page(client, token, site_root):
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="To action-delete",
    )
    result = call_tool(client, token, "pages_actions_delete", page_id=created["id"])
    assert result["deleted"] is True
    assert not Page.objects.filter(pk=created["id"]).exists()


def test_page_write_tools_annotations(client, token, site_root):

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    # Create/update are plain WRITE tools.
    for name in ("pages_create", "pages_update"):
        ann = tools[name]
        assert ann.get("readOnlyHint") is not True
        assert ann.get("destructiveHint") is not True
    # Deletes are destructive, driving client confirmation UX.
    for name in ("pages_delete", "pages_actions_delete"):
        assert tools[name].get("destructiveHint") is True
