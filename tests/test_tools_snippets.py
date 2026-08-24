import pytest

from test_protocol import call_tool, call_tool_raw
from wagtail.models import Locale

from wagtail_mcp.test.models import DraftablePerson, Person


pytestmark = pytest.mark.django_db(transaction=True)

PERSON = "wagtail_mcp_test.Person"
DRAFTABLE = "wagtail_mcp_test.DraftablePerson"


@pytest.fixture(autouse=True)
def locale_baseline():
    """Ensure a default Locale plus an 'fr' locale exist.

    ``transaction=True`` truncates the DB between tests, wiping the
    migration-seeded default Locale. A Locale is required to create
    TranslatableMixin snippets (their ``locale`` is auto-assigned from the
    default on ``pre_save``); ``fr`` is needed by the copy_for_translation
    test.
    """
    Locale.objects.get_or_create(language_code="en")
    Locale.objects.get_or_create(language_code="fr")


def test_snippet_tool_annotations(client, token):
    # Read tools advertised readOnly, writes writable, deletes destructive —
    # MCP annotations that drive client UX (confirm prompts).
    from test_protocol import TOOLS_LIST, post

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    for name in ("snippets_list", "snippets_detail", "snippets_revisions_list"):
        assert tools[name].get("readOnlyHint") is True
    for name in (
        "snippets_create",
        "snippets_update",
        "snippets_actions_publish",
        "snippets_actions_revert",
        "snippets_actions_copy_for_translation",
    ):
        assert tools[name].get("readOnlyHint") is not True
        assert tools[name].get("destructiveHint") is not True
    for name in ("snippets_delete", "snippets_actions_delete"):
        assert tools[name].get("destructiveHint") is True


def test_snippets_list_and_detail(client, token):
    created = call_tool(
        client, token, "snippets_create", type=PERSON, data={"name": "Ada"}
    )
    assert created["name"] == "Ada"
    assert created["meta"]["type"] == PERSON

    detail = call_tool(
        client, token, "snippets_detail", type=PERSON, snippet_id=created["id"]
    )
    assert detail["id"] == created["id"]
    assert detail["name"] == "Ada"

    listed = call_tool(client, token, "snippets_list", type=PERSON, limit=20)
    assert listed["count"] >= 1
    names = [item["name"] for item in listed["items"]]
    assert "Ada" in names
    assert listed["items"][0]["meta"]["type"] == PERSON


def test_snippets_list_search_nonindexed_errors(client, token):
    # search only works on snippet models that declare ``search_fields``; the
    # test ``Person`` model does not, so the API rejects it cleanly. This
    # pins the real behavior (a usable error, not a crash) and that the tool
    # forwards the search param.
    call_tool(client, token, "snippets_create", type=PERSON, data={"name": "Bob Smith"})
    raw = call_tool_raw(client, token, "snippets_list", type=PERSON, search="Smith")
    assert raw["isError"] is True
    assert "422" in raw["content"][0]["text"]
    assert "not indexed for search" in raw["content"][0]["text"]


def test_snippets_create_unknown_field_errors(client, token):
    raw = call_tool_raw(
        client, token, "snippets_create", type=PERSON, data={"nonexistent": "x"}
    )
    assert raw["isError"] is True
    assert "422" in raw["content"][0]["text"]


def test_snippets_update(client, token):
    created = call_tool(
        client, token, "snippets_create", type=PERSON, data={"name": "Draft"}
    )
    updated = call_tool(
        client,
        token,
        "snippets_update",
        type=PERSON,
        snippet_id=created["id"],
        data={"name": "Final"},
    )
    assert updated["name"] == "Final"
    detail = call_tool(
        client, token, "snippets_detail", type=PERSON, snippet_id=created["id"]
    )
    assert detail["name"] == "Final"


def test_snippets_error_paths(client, token):
    # Bogus type string (unknown model label) → 422, not a crash.
    raw = call_tool_raw(client, token, "snippets_list", type="no.such.Type")
    assert raw["isError"] is True
    assert "422" in raw["content"][0]["text"]

    # Type strings are case-sensitive (the API matches app_label.ModelName).
    raw = call_tool_raw(client, token, "snippets_list", type="wagtail_mcp_test.person")
    assert raw["isError"] is True
    assert "422" in raw["content"][0]["text"]

    # Unknown snippet id → 404.
    raw = call_tool_raw(
        client, token, "snippets_detail", type=PERSON, snippet_id=999999
    )
    assert raw["isError"] is True
    assert "404" in raw["content"][0]["text"]


def test_snippets_delete(client, token):
    created = call_tool(
        client, token, "snippets_create", type=PERSON, data={"name": "Ephemeral"}
    )
    result = call_tool(
        client, token, "snippets_delete", type=PERSON, snippet_id=created["id"]
    )
    assert result["deleted"] is True
    assert not Person.objects.filter(pk=created["id"]).exists()


def test_snippets_actions_delete(client, token):
    created = call_tool(
        client, token, "snippets_create", type=PERSON, data={"name": "Ephemeral"}
    )
    result = call_tool(
        client, token, "snippets_actions_delete", type=PERSON, snippet_id=created["id"]
    )
    assert result["deleted"] is True
    assert not Person.objects.filter(pk=created["id"]).exists()


# --- Draftable / revisable / translatable action chain -----------------------


def _create_draftable(client, token, name="Draft"):
    return call_tool(
        client, token, "snippets_create", type=DRAFTABLE, data={"name": name}
    )


def test_draftable_publish_unpublish(client, token):
    created = _create_draftable(client, token)
    obj = DraftablePerson.objects.get(pk=created["id"])
    assert obj.live is False

    call_tool(
        client,
        token,
        "snippets_actions_publish",
        type=DRAFTABLE,
        snippet_id=created["id"],
    )
    obj.refresh_from_db()
    assert obj.live is True

    call_tool(
        client,
        token,
        "snippets_actions_unpublish",
        type=DRAFTABLE,
        snippet_id=created["id"],
    )
    obj.refresh_from_db()
    assert obj.live is False


def test_draftable_create_with_publish_action(client, token):
    # publish=True in the create body publishes immediately (meta.action).
    created = call_tool(
        client,
        token,
        "snippets_create",
        type=DRAFTABLE,
        data={"name": "Straight to live"},
        publish=True,
    )
    obj = DraftablePerson.objects.get(pk=created["id"])
    assert obj.live is True


def test_draftable_revert(client, token):
    created = _create_draftable(client, token, name="First version")
    pid = created["id"]

    # A plain (non-draftstate) snippet can't be reverted — the API rejects the
    # action endpoint with 422 — but a draftable one can.
    call_tool(
        client,
        token,
        "snippets_update",
        type=DRAFTABLE,
        snippet_id=pid,
        data={"name": "Second version"},
    )

    revs = call_tool(
        client, token, "snippets_revisions_list", type=DRAFTABLE, snippet_id=pid
    )
    assert revs["count"] == 2
    assert {item["object_str"] for item in revs["items"]} == {
        "First version",
        "Second version",
    }

    # Revert to the first-state revision restores that content as the draft.
    first_id = next(
        item["id"] for item in revs["items"] if item["object_str"] == "First version"
    )
    reverted = call_tool(
        client,
        token,
        "snippets_actions_revert",
        type=DRAFTABLE,
        snippet_id=pid,
        revision_id=first_id,
    )
    assert reverted["name"] == "First version"

    # Revising then reading the draft surfaces the reverted content.
    after = call_tool(
        client,
        token,
        "snippets_detail",
        type=DRAFTABLE,
        snippet_id=pid,
        version="draft",
    )
    assert after["name"] == "First version"


def test_snippets_revisions_detail(client, token):
    created = _create_draftable(client, token, name="V1")
    pid = created["id"]
    call_tool(
        client,
        token,
        "snippets_update",
        type=DRAFTABLE,
        snippet_id=pid,
        data={"name": "V2"},
    )
    revs = call_tool(
        client, token, "snippets_revisions_list", type=DRAFTABLE, snippet_id=pid
    )
    latest = max(revs["items"], key=lambda i: i["id"])
    detail = call_tool(
        client,
        token,
        "snippets_revisions_detail",
        type=DRAFTABLE,
        snippet_id=pid,
        revision_id=latest["id"],
    )
    assert detail["object_str"] == "V2"
    assert detail["content_object"]["name"] == "V2"


def test_copy_for_translation(client, token):
    created = _create_draftable(client, token, name="Original")
    pid = created["id"]
    copied = call_tool(
        client,
        token,
        "snippets_actions_copy_for_translation",
        type=DRAFTABLE,
        snippet_id=pid,
        locale="fr",
    )
    # A new snippet is created; the original is left alone.
    assert copied["id"] != pid
    assert copied["name"] == "Original"
    assert DraftablePerson.objects.filter(pk=copied["id"]).exists()
    assert (
        DraftablePerson.objects.filter(pk=copied["id"])[0].locale.language_code == "fr"
    )


def test_actions_rejected_for_plain_snippet(client, token):
    # publish/revert need the relevant mixin; calling it on a plain snippet
    # surface returns the API's 422 rather than silently doing nothing.
    created = call_tool(
        client, token, "snippets_create", type=PERSON, data={"name": "Plain"}
    )
    raw = call_tool_raw(
        client, token, "snippets_actions_publish", type=PERSON, snippet_id=created["id"]
    )
    assert raw["isError"] is True
    assert "422" in raw["content"][0]["text"]


def test_copy_for_translation_unknown_locale(client, token):
    created = _create_draftable(client, token)
    raw = call_tool_raw(
        client,
        token,
        "snippets_actions_copy_for_translation",
        type=DRAFTABLE,
        snippet_id=created["id"],
        locale="xx",
    )
    assert raw["isError"] is True
    assert "404" in raw["content"][0]["text"]
