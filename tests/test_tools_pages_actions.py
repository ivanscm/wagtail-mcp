import itertools

import pytest

from django.test import override_settings
from test_protocol import TOOLS_LIST, call_tool, call_tool_raw, post
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
    """A deterministic site: root page, default site on a unique hostname, one
    published ContentPage child."""
    root = Page.objects.get(depth=1)
    site_root = ContentPage(title="Site root", slug=f"root-{next(_hostname_counter)}")
    root.add_child(instance=site_root)
    hostname = f"site-{next(_hostname_counter)}.test"
    Site.objects.create(hostname=hostname, root_page=site_root, is_default_site=True)
    page = ContentPage(title="The Target", slug="the-target")
    site_root.add_child(instance=page)
    page.save_revision().publish()
    return site_root


def _target(site_root):
    """The created/published ContentPage child of site_root."""
    return site_root.get_children().get(slug="the-target")


def test_page_action_tools_annotations(client, token):
    # Every action tool must be advertised with the expected MCP annotation,
    # so clients apply the right confirmation UX (destructive actions prompt).
    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }

    def ann(name):
        assert name in tools, f"{name} missing from tools/list"
        return tools[name]

    assert ann("pages_actions_publish").get("readOnlyHint") is not True
    assert ann("pages_actions_unpublish").get("destructiveHint") is True
    for name in (
        "pages_actions_publish",
        "pages_actions_copy",
        "pages_actions_move",
        "pages_actions_revert",
        "pages_actions_convert_alias",
        "pages_actions_create_alias",
        "pages_actions_copy_for_translation",
    ):
        assert ann(name).get("destructiveHint") is not True
    for name in ("pages_revisions_list", "pages_revisions_detail"):
        assert ann(name).get("readOnlyHint") is True


def test_publish_publishes_draft(client, token, site_root):
    # Create a fresh draft (not published) so there is something to publish.
    created = call_tool(
        client,
        token,
        "pages_create",
        type="wagtail_mcp_test.ContentPage",
        parent_id=site_root.pk,
        title="Draft to publish",
    )
    created_pk = created["id"]
    assert Page.objects.get(pk=created_pk).live is False

    result = call_tool(client, token, "pages_actions_publish", page_id=created_pk)
    assert result["id"] == created_pk
    assert Page.objects.get(pk=created_pk).live is True


def test_unpublish_then_unpublish_again_errors(client, token, site_root):
    target = _target(site_root)

    result = call_tool(
        client, token, "pages_actions_unpublish", page_id=target.pk, recursive=False
    )
    assert result["id"] == target.pk
    assert Page.objects.get(pk=target.pk).live is False

    # Repeating the unpublish on an already-unpublished page is NOT idempotent:
    # the API refuses with a 403 (the page is no longer live, so the unpublish
    # permission check fails). Pinned here so agent-facing behavior is explicit.
    raw = call_tool_raw(
        client, token, "pages_actions_unpublish", page_id=target.pk, recursive=False
    )
    assert raw["isError"] is True
    assert "permission to unpublish" in raw["content"][0]["text"]


def test_full_editorial_chain_revert(client, token, site_root):
    """create draft → publish → detail(live) → edit → revisions_list → revert
    → confirm original content restored."""
    target = _target(site_root)
    page_id = target.pk
    original_title = target.title  # fixture publishes "The Target" (revision 1)

    # Edit to a distinct draft version (not published).
    call_tool(client, token, "pages_update", page_id=page_id, title="Edited title")
    call_tool(client, token, "pages_actions_publish", page_id=page_id)

    # Newer draft edit.
    call_tool(client, token, "pages_update", page_id=page_id, title="Latest draft")

    revisions = call_tool(client, token, "pages_revisions_list", page_id=page_id)
    assert revisions["count"] >= 2
    rev_ids = [r["id"] for r in revisions["items"]]
    # The earliest (min) revision holds the original published content.
    first_rev = min(rev_ids)

    detail = call_tool(
        client, token, "pages_revisions_detail", page_id=page_id, revision_id=first_rev
    )
    assert detail["id"] == first_rev
    assert detail["content_object"]["title"] == original_title

    restored = call_tool(
        client,
        token,
        "pages_actions_revert",
        page_id=page_id,
        revision_id=first_rev,
    )
    assert restored["id"] == page_id
    # Draft now shows the reverted-to content.
    draft = call_tool(client, token, "pages_detail", page_id=page_id, version="draft")
    assert draft["title"] == original_title


def test_revert_bogus_revision_errors(client, token, site_root):
    target = _target(site_root)
    raw = call_tool_raw(
        client, token, "pages_actions_revert", page_id=target.pk, revision_id=999999
    )
    assert raw["isError"] is True
    assert "404" in raw["content"][0]["text"]


def test_copy_and_move(client, token, site_root):
    target = _target(site_root)
    # A second parent page to copy under + move around.
    root = Page.objects.get(depth=1)
    parent_a = ContentPage(title="Parent A", slug="parent-a")
    root.add_child(instance=parent_a)
    parent_b = ContentPage(title="Parent B", slug="parent-b")
    root.add_child(instance=parent_b)

    # Copy places the copy under parent_a (destination).
    copied = call_tool(
        client,
        token,
        "pages_actions_copy",
        page_id=target.pk,
        destination_id=parent_a.pk,
    )
    copied_pk = copied["id"]
    assert Page.objects.get(pk=copied_pk).get_parent().pk == parent_a.pk

    # Move requires a child `position` to place the page UNDER the destination;
    # otherwise it becomes a sibling of it. Use last-child to place under parent_b.
    moved = call_tool(
        client,
        token,
        "pages_actions_move",
        page_id=copied_pk,
        destination_id=parent_b.pk,
        position="last-child",
    )
    assert moved["id"] == copied_pk
    assert Page.objects.get(pk=copied_pk).get_parent().pk == parent_b.pk


def test_create_alias_then_convert(client, token, site_root):
    target = _target(site_root)

    alias = call_tool(client, token, "pages_actions_create_alias", page_id=target.pk)
    alias_pk = alias["id"]
    assert Page.objects.get(pk=alias_pk).alias_of_id == target.pk

    converted = call_tool(
        client, token, "pages_actions_convert_alias", page_id=alias_pk
    )
    assert converted["id"] == alias_pk
    assert Page.objects.get(pk=alias_pk).alias_of_id is None


@override_settings(WAGTAIL_I18N_ENABLED=True)
def test_copy_for_translation(client, token, site_root):
    target = _target(site_root)
    fr_locale = Locale.objects.create(language_code="fr")

    # copy_parents=True so untranslated ancestors (the site root) are copied
    # into the target locale too.
    result = call_tool(
        client,
        token,
        "pages_actions_copy_for_translation",
        page_id=target.pk,
        locale="fr",
        copy_parents=True,
    )
    new_pk = result["id"]
    new_page = Page.objects.get(pk=new_pk)
    assert new_page.locale_id == fr_locale.pk
    assert new_page.pk != target.pk
    # The translated page gets a translated ancestor chain, so its immediate
    # parent differs from the original's (a freshly copied fr parent).
    assert new_page.get_parent().locale_id == fr_locale.pk
