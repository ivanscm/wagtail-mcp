import base64

import pytest

from test_protocol import call_tool, call_tool_raw
from wagtail.documents import get_document_model


pytestmark = pytest.mark.django_db(transaction=True)

# A minimal text document's base64. Wagtail's document upload accepts any file
# type (unlike images, which Pillow validates), so plain ASCII bytes are valid.
TXT_BASE64 = base64.b64encode(b"Hello, document world.").decode("ascii")


@pytest.fixture(autouse=True)
def collection_baseline():
    """Ensure the root Collection exists.

    ``transaction=True`` truncates the DB between tests, wiping the
    migration-seeded root collection that ``Document.get_root_collection_id``
    assumes, so each test reseeds it here (mirroring the wagtailcore 0025
    migration).
    """
    from wagtail.models import Collection

    if not Collection.objects.filter(depth=1).exists():
        Collection.objects.create(name="Root", path="0001", depth=1, numchild=0)


def test_document_tools_annotations(client, token):
    from test_protocol import TOOLS_LIST, post

    response = post(client, TOOLS_LIST, token)
    tools = {
        t["name"]: t.get("annotations", {}) for t in response.json()["result"]["tools"]
    }
    assert tools["documents_list"].get("readOnlyHint") is True
    assert tools["documents_detail"].get("readOnlyHint") is True
    assert tools["documents_create"].get("readOnlyHint") is not True
    assert tools["documents_update"].get("readOnlyHint") is not True
    assert tools["documents_delete"].get("destructiveHint") is True


def test_documents_list_empty(client, token):
    result = call_tool(client, token, "documents_list", limit=20, offset=0)
    assert result["count"] == 0
    assert result["items"] == []


def test_documents_create_and_detail(client, token):
    created = call_tool(
        client,
        token,
        "documents_create",
        title="Readme",
        content_base64=TXT_BASE64,
        filename="readme.txt",
    )
    assert created["title"] == "Readme"
    document_id = created["id"]

    detail = call_tool(client, token, "documents_detail", document_id=document_id)
    assert detail["id"] == document_id
    assert detail["title"] == "Readme"
    assert detail["meta"]["type"] == "wagtaildocs.Document"
    assert detail["meta"]["download_url"].endswith(".txt")


def test_documents_list_includes_created(client, token):
    call_tool(
        client,
        token,
        "documents_create",
        title="Listed",
        content_base64=TXT_BASE64,
        filename="listed.txt",
    )
    result = call_tool(client, token, "documents_list", limit=20)
    titles = [item["title"] for item in result["items"]]
    assert "Listed" in titles


def test_documents_update(client, token):
    created = call_tool(
        client,
        token,
        "documents_create",
        title="Before",
        content_base64=TXT_BASE64,
        filename="upd.txt",
    )
    updated = call_tool(
        client,
        token,
        "documents_update",
        document_id=created["id"],
        title="After",
    )
    assert updated["title"] == "After"
    assert get_document_model().objects.get(pk=created["id"]).title == "After"


def test_documents_delete(client, token):
    created = call_tool(
        client,
        token,
        "documents_create",
        title="Doomed",
        content_base64=TXT_BASE64,
        filename="doom.txt",
    )
    result = call_tool(client, token, "documents_delete", document_id=created["id"])
    assert result["deleted"] is True
    raw = call_tool_raw(client, token, "documents_detail", document_id=created["id"])
    assert raw["isError"] is True


def test_documents_content_type_from_pdf_extension(client, token):
    # .pdf is a recognised extension; the document uploads and keeps .pdf.
    pdfish = base64.b64encode(b"%PDF-1.4 hello").decode("ascii")
    created = call_tool(
        client,
        token,
        "documents_create",
        title="PdfDoc",
        content_base64=pdfish,
        filename="doc.pdf",
    )
    assert created["id"]
    assert created["meta"]["download_url"].endswith(".pdf")


def test_documents_create_invalid_base64_is_error(client, token):
    raw = call_tool_raw(
        client,
        token,
        "documents_create",
        title="Broken",
        content_base64="not!base64!!",
        filename="x.txt",
    )
    assert raw["isError"] is True
    assert "base64" in raw["content"][0]["text"]


def test_documents_detail_missing_is_error(client, token):
    raw = call_tool_raw(client, token, "documents_detail", document_id=999999)
    assert raw["isError"] is True


def test_documents_create_passes_collection_id_through(client, token):
    """An explicit ``collection_id`` is forwarded and stored on the document."""
    from wagtail.models import Collection

    root = Collection.get_first_root_node()
    child = root.add_child(name="Reports")
    created = call_tool(
        client,
        token,
        "documents_create",
        title="Quarterly",
        content_base64=TXT_BASE64,
        filename="quarterly.txt",
        collection_id=child.id,
    )
    assert created["title"] == "Quarterly"
    doc = get_document_model().objects.get(pk=created["id"])
    assert doc.collection_id == child.id
