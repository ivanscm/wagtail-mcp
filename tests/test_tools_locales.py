import pytest

from test_protocol import TOOLS_LIST, call_tool, call_tool_raw, post
from wagtail.models import Locale


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def locale_baseline():
    """Ensure a default (English) locale exists.

    ``transaction=True`` truncates the DB between tests, wiping the location of
    Wagtail's default locale, so each test reseeds it.
    """
    if not Locale.objects.exists():
        Locale.objects.create(language_code="en")
    yield
    # Re-prune any locales added by the test so the next test starts clean,
    # and always keep exactly one default (English) locale.
    Locale.objects.exclude(language_code="en").delete()


@pytest.fixture
def default_locale_id(locale_baseline):
    return Locale.objects.get(language_code="en").pk


def test_locale_tools_annotations(client, token):

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    for name in ("locales_list", "locales_detail"):
        assert tools[name].get("readOnlyHint") is True
    assert tools["locales_create"].get("readOnlyHint") is not True
    assert tools["locales_update"].get("readOnlyHint") is not True
    assert tools["locales_delete"].get("destructiveHint") is True


def test_locales_list_has_baseline(client, token, default_locale_id):
    result = call_tool(client, token, "locales_list", limit=20, offset=0)
    codes = [item["language_code"] for item in result["items"]]
    assert "en" in codes
    assert result["count"] >= 1


def test_locales_create_detail(client, token, default_locale_id):
    created = call_tool(client, token, "locales_create", language_code="fr")
    assert created["language_code"] == "fr"
    assert created["id"]
    assert created["meta"]["type"] == "wagtailcore.Locale"

    detail = call_tool(client, token, "locales_detail", locale_id=created["id"])
    assert detail["id"] == created["id"]
    assert detail["language_code"] == "fr"


def test_locales_list_includes_created(client, token, default_locale_id):
    call_tool(client, token, "locales_create", language_code="de")
    result = call_tool(client, token, "locales_list", limit=20)
    codes = [item["language_code"] for item in result["items"]]
    assert "de" in codes


def test_locales_update(client, token, default_locale_id):
    created = call_tool(client, token, "locales_create", language_code="fr")
    updated = call_tool(
        client, token, "locales_update", locale_id=created["id"], language_code="pt"
    )
    assert updated["language_code"] == "pt"


def test_locales_delete(client, token, default_locale_id):
    created = call_tool(client, token, "locales_create", language_code="fr")
    result = call_tool(client, token, "locales_delete", locale_id=created["id"])
    assert result["deleted"] is True
    assert not Locale.objects.filter(pk=created["id"]).exists()


def test_locales_delete_last_remaining_is_error(client, token, default_locale_id):
    # Deleting the only remaining locale is refused by the v3 API
    # ("there are no other locales"), which surfaces as a 422 tool error.
    raw = call_tool_raw(client, token, "locales_delete", locale_id=default_locale_id)
    assert raw["isError"] is True
    text = raw["content"][0]["text"]
    assert "422" in text or "Unprocessable" in text or "cannot be deleted" in text
