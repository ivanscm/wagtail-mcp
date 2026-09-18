import pytest

from test_protocol import call_tool, call_tool_raw
from wagtail.images import get_image_model


pytestmark = pytest.mark.django_db(transaction=True)

# 1x1 transparent GIF, the smallest valid image Wagtail's Pillow validation
# accepts (used throughout the dispatch test suite).
GIF_BASE64 = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="


@pytest.fixture(autouse=True)
def collection_baseline():
    """Ensure the root Collection exists.

    ``transaction=True`` truncates the DB between tests, wiping the
    migration-seeded root collection that ``Image.get_root_collection_id``
    assumes, so each test reseeds it here (mirroring the wagtailcore 0025
    migration).
    """
    from wagtail.models import Collection

    if not Collection.objects.filter(depth=1).exists():
        Collection.objects.create(name="Root", path="0001", depth=1, numchild=0)


def test_image_tools_annotations(client, token):
    # Read tools must be advertised readOnly, write tools writable, delete
    # destructive — MCP annotations that drive client UX (confirm prompts).
    from test_protocol import TOOLS_LIST, post

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    assert tools["images_list"].get("readOnlyHint") is True
    assert tools["images_detail"].get("readOnlyHint") is True
    assert tools["images_create"].get("readOnlyHint") is not True
    assert tools["images_update"].get("readOnlyHint") is not True
    assert tools["images_delete"].get("destructiveHint") is True
    assert tools["images_list"].get("destructiveHint") is not True


def test_images_list_empty(client, token):
    result = call_tool(client, token, "images_list", limit=20, offset=0)
    assert result["count"] == 0
    assert result["items"] == []
    assert result["next_offset"] is None


def test_images_create_and_detail(client, token):
    created = call_tool(
        client,
        token,
        "images_create",
        title="Pixel",
        content_base64=GIF_BASE64,
        filename="pixel.gif",
    )
    assert created["title"] == "Pixel"
    image_id = created["id"]

    detail = call_tool(client, token, "images_detail", image_id=image_id)
    assert detail["id"] == image_id
    assert detail["title"] == "Pixel"
    assert detail["meta"]["type"] == "wagtailimages.Image"
    assert detail["meta"]["download_url"]
    # Server-side image validation ran: dimensions were parsed from the GIF.
    assert detail["width"] == 1 and detail["height"] == 1
    # Detail responses pass every API field through: focal point keys are
    # present even when null, and the collection is identified.
    assert detail["focal_point_x"] is None
    assert detail["focal_point_y"] is None
    assert detail["collection"]["id"]


def test_images_list_includes_created(client, token):
    call_tool(
        client,
        token,
        "images_create",
        title="Listed",
        content_base64=GIF_BASE64,
        filename="listed.gif",
    )
    result = call_tool(client, token, "images_list", limit=20)
    titles = [item["title"] for item in result["items"]]
    assert "Listed" in titles
    assert result["count"] >= 1


def test_images_update(client, token):
    created = call_tool(
        client,
        token,
        "images_create",
        title="Before",
        content_base64=GIF_BASE64,
        filename="upd.gif",
    )
    updated = call_tool(
        client, token, "images_update", image_id=created["id"], title="After"
    )
    assert updated["title"] == "After"
    detail = call_tool(client, token, "images_detail", image_id=created["id"])
    assert detail["title"] == "After"
    assert get_image_model().objects.get(pk=created["id"]).title == "After"


def test_images_create_and_update_description(client, token):
    created = call_tool(
        client,
        token,
        "images_create",
        title="Described",
        description="A tiny pixel.",
        content_base64=GIF_BASE64,
        filename="desc.gif",
    )
    image = get_image_model().objects.get(pk=created["id"])
    assert image.description == "A tiny pixel."
    assert created["description"] == "A tiny pixel."

    # PATCH semantics: updating the description leaves the title alone, and
    # an update without a title is valid.
    updated = call_tool(
        client,
        token,
        "images_update",
        image_id=created["id"],
        description="Renamed alt",
    )
    assert updated["title"] == "Described"
    assert updated["description"] == "Renamed alt"
    image.refresh_from_db()
    assert image.title == "Described"
    assert image.description == "Renamed alt"


def test_images_delete(client, token):
    created = call_tool(
        client,
        token,
        "images_create",
        title="Doomed",
        content_base64=GIF_BASE64,
        filename="doom.gif",
    )
    result = call_tool(client, token, "images_delete", image_id=created["id"])
    assert result["deleted"] is True
    raw = call_tool_raw(client, token, "images_detail", image_id=created["id"])
    assert raw["isError"] is True


def test_images_content_type_inferred_from_name(client, token):
    # No content_type passed - inferred from the .png extension; Pillow still
    # validates the actual bytes, so PNG bytes are used.
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    created = call_tool(
        client,
        token,
        "images_create",
        title="Inferred",
        content_base64=png,
        filename="pixel.png",
    )
    assert created["id"]
    assert created["meta"]["download_url"].endswith(".png")


def test_images_create_invalid_base64_is_error(client, token):
    raw = call_tool_raw(
        client,
        token,
        "images_create",
        title="Broken",
        content_base64="not!base64!!",
        filename="x.gif",
    )
    assert raw["isError"] is True
    assert "base64" in raw["content"][0]["text"]


def test_images_create_invalid_content_type_is_error(client, token):
    raw = call_tool_raw(
        client,
        token,
        "images_create",
        title="NoExt",
        content_base64=GIF_BASE64,
        filename="pixel.unknown",
    )
    assert raw["isError"] is True
    assert "content type" in raw["content"][0]["text"]


def test_images_detail_missing_is_error(client, token):
    raw = call_tool_raw(client, token, "images_detail", image_id=999999)
    assert raw["isError"] is True
    assert (
        "404" in raw["content"][0]["text"] or "Not Found" in raw["content"][0]["text"]
    )
