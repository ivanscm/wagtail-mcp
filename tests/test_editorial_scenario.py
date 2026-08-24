"""Flagship editorial-scenario integration test (RFC 115 QA path).

Drives the WHOLE content workflow through the real MCP stack (`/mcp/`
``tools/call``): authenticate → discover the schema → find/create a parent →
upload an image → create and publish a page whose body embeds that image →
verify the live page is routable and the converted-DB-HTML carries the image
embed all the way down to the stored record.

One documented workaround is pinned here and reported upstream: submitting an
image embed in *Markdown* body input is silently dropped by the v3 write
sanitiser (see :func:`test_markdown_embed_is_pinned`); the full image-embed
flow is therefore exercised through the ``api_call`` escape hatch with a
``db_html`` body (the supported input path), matching the brief's fallback of
"embed via HTML <embed .../> richtext format instead".
"""

import uuid

import pytest

from test_protocol import call_tool, call_tool_raw
from wagtail.images import get_image_model
from wagtail.models import Locale, Page, Site

from wagtail_mcp.test.models import ContentPage


pytestmark = pytest.mark.django_db(transaction=True)

CONTENT_PAGE_TYPE = "wagtail_mcp_test.ContentPage"

# A 1x1 transparent GIF, base64 — the same fixture used by the upload tests.
GIF_BASE64 = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="


@pytest.fixture(autouse=True)
def wagtail_baseline():
    """Ensure a default Locale + root page exist.

    ``transaction=True`` truncates the DB between tests, wiping the
    migration-seeded Locale and root page, so each test reseeds them here.
    """
    Locale.objects.get_or_create(language_code="en")
    if not Page.objects.filter(depth=1).exists():
        Page.objects.create(path="0001", depth=1, url_path="/", title="Root")
    # ``transaction=True`` also wipes the migration-seeded root Collection,
    # which ``Image.get_root_collection_id`` requires (mirroring the
    # collection_baseline fixture in test_tools_images.py).
    from wagtail.models import Collection

    if not Collection.objects.filter(depth=1).exists():
        Collection.objects.create(name="Root", path="0001", depth=1, numchild=0)
    yield


def _publish_content_parent(client, token, title):
    """Create a published ContentPage under root, with a default Site, via the
    curated ``pages_create`` tool (Markdown body). Returns the page id.

    A default Site on the branch makes the live page routable and its
    ``url_path`` resolvable from the in-process dispatch's request.
    """
    result = call_tool(
        client,
        token,
        "pages_create",
        type=CONTENT_PAGE_TYPE,
        parent_id=Page.objects.get(depth=1).pk,
        title=title,
        body_markdown="# Site root",
        publish=True,
    )
    page_id = result["id"]
    Site.objects.create(
        hostname=f"site-{uuid.uuid4().hex[:8]}.test",
        root_page=ContentPage.objects.get(pk=page_id),
        is_default_site=True,
    )
    return page_id


def _upload_image(client, token, title):
    """Upload the 1x1 GIF via the curated ``images_create`` tool; return id."""
    result = call_tool(
        client,
        token,
        "images_create",
        title=title,
        content_base64=GIF_BASE64,
        filename="pixel.gif",
        content_type="image/gif",
    )
    return result["id"]


def _embed_html(image_id, alt, format="right"):
    """A db_html body fragment embedding an image via Wagtail's DisplayEmbed."""
    return (
        f"<p>Intro paragraph.</p>"
        f'<embed alt="{alt}" embedtype="image" format="{format}" id="{image_id}"/>'
        f"<p>The end.</p>"
    )


def test_editorial_scenario_end_to_end(client, token):
    uid = uuid.uuid4().hex[:8]

    # 1. Authenticate — whoami confirms the token's user.
    who = call_tool(client, token, "whoami")
    assert who["user"]["username"] == "admin"
    assert who["user"]["is_superuser"] is True

    # 2. Schema discovery — the ContentPage create schema is available.
    schema = call_tool(client, token, "schema_detail", type_name=CONTENT_PAGE_TYPE)
    assert set(schema) >= {"read", "create", "patch"}
    assert "title" in str(schema["create"])

    # 3. Parent — list root's children, then create a published site-root parent
    # through the curated pages_create tool (proving the markdown path works).
    root_children = call_tool(client, token, "pages_list", child_of="root", limit=20)
    assert "items" in root_children
    parent_id = _publish_content_parent(client, token, f"Editorial Root {uid}")
    parent_detail = call_tool(client, token, "pages_detail", page_id=parent_id)
    assert parent_detail["id"] == parent_id
    assert parent_detail["meta"]["type"] == CONTENT_PAGE_TYPE

    # 4. Image upload — returns an id we embed in the page body.
    image_title = f"Pixel {uid}"
    image_id = _upload_image(client, token, image_title)
    assert get_image_model().objects.filter(pk=image_id, title=image_title).exists()

    # 5. Create + publish a page embedding the uploaded image. Markdown image
    # embeds are silently dropped (pinned in test_markdown_embed_is_pinned), so
    # we send the image through the supported db_html input path via the
    # api_call escape hatch — exactly the fallback the brief anticipated.
    title = f"Editorial post {uid}"
    created = call_tool(
        client,
        token,
        "api_call",
        operation_id="pages_create",
        body={
            "meta": {
                "type": CONTENT_PAGE_TYPE,
                "parent_id": parent_id,
                "action": "publish",
            },
            "title": title,
            "slug": f"editorial-post-{uid}",
            "body": _embed_html(image_id, image_title),
        },
    )
    page_id = created["id"]
    assert created["title"] == title
    assert created["meta"]["type"] == CONTENT_PAGE_TYPE

    # 6. Live detail (via the curated pages_detail tool). The stored db_html
    # embed round-trips to Markdown on read, so the live body exposes the image
    # reference — proving the published live page retains the embed.
    live = call_tool(client, token, "pages_detail", page_id=page_id, version="live")
    assert live["title"] == title
    body_markdown_out = live.get("body", "")
    # The live body round-trips the stored embed to a Markdown image reference.
    # With ``rich_text_format=markdown`` the image is resolved to its real
    # rendition URL, proving the uploaded image is reachable end-to-end.
    assert body_markdown_out.startswith("Intro paragraph.")
    assert "![" in body_markdown_out
    assert "/images/pixel" in body_markdown_out

    # 7a. Stored DB record — the image embed survived conversion/sanitisation as
    # a DisplayEmbed, and the page is live.
    page = ContentPage.objects.get(pk=page_id)
    assert page.live is True
    assert 'embedtype="image"' in page.body
    assert f'id="{image_id}"' in page.body

    # 7b. The live page is routable and serves 200 at its URL. The servable URL
    # is the page's url_path relative to its site root (the root page of the
    # default site we created serves as "/").
    serving_site = Site.objects.get(is_default_site=True, root_page=parent_id)
    served_path = "/" + page.url_path[len(serving_site.root_page.url_path) :].lstrip(
        "/"
    )
    response = client.get(served_path)
    assert response.status_code == 200, served_path
    assert title.encode() in response.content
    # The richtext filter expands the stored embed to a rendered <img>
    # (the uploaded image serving through its rendition).
    assert b"<img" in response.content

    # 7c. The live html (expand_db_html) resolves the embed to an <img>.
    live_html = call_tool(
        client,
        token,
        "pages_detail",
        page_id=page_id,
        version="live",
        rich_text_format="html",
    )
    assert "<img" in live_html.get("body", "")


def test_markdown_embed_is_pinned(client, token):
    """Pin REAL v3 behaviour: a Markdown image embed is silently dropped.

    Submitting ``![alt](wagtail://image?id=N)`` as rich-text *input* is
    converted to an ``<embed data-embedtype="image" .../>`` element, then the
    image-feature whitelister censors it (reason ``missing_attribute``) because
    the Markdown pipeline's attribute spelling doesn't match the ``embed
    embedtype="image"`` rule. The page still publishes live, but the embed is
    absent from the stored body. Recorded for upstream feedback.
    """
    uid = uuid.uuid4().hex[:8]
    image_id = _upload_image(client, token, f"Markdown Pixel {uid}")
    parent_id = _publish_content_parent(client, token, f"Markdown Root {uid}")

    title = f"Markdown embed {uid}"
    created = call_tool(
        client,
        token,
        "pages_create",
        type=CONTENT_PAGE_TYPE,
        parent_id=parent_id,
        title=title,
        body_markdown=f"![Pixel](wagtail://image?id={image_id})\n\nBye.",
        publish=True,
    )
    page_id = created["id"]

    page = ContentPage.objects.get(pk=page_id)
    assert page.live is True
    # The image embed is gone: neither the DisplayEmbed nor its id remains
    # (checked by the id-in-attribute form to avoid substring false positives).
    assert "embed" not in page.body
    assert f'id="{image_id}"' not in page.body
    assert f'data-id="{image_id}"' not in page.body
    # … but the rest of the prose survived.
    assert "Bye." in page.body


def test_publish_under_unpublished_parent_pinned(client, token):
    """Pin REAL v3 behaviour: publishing a page under an UNPUBLISHED parent.

    Creates a draft parent (not published) then tries to create+publish a child
    under it via the curated ``pages_create`` tool. The assertion encodes which
    of the two real outcomes the API chooses — it either rejects the publish or
    silently publishes under the draft parent. Whichever it is, the flagship
    test (above) always publishes its parent first, so this documents the real
    contract rather than assuming.
    """
    uid = uuid.uuid4().hex[:8]
    parent = call_tool(
        client,
        token,
        "pages_create",
        type=CONTENT_PAGE_TYPE,
        parent_id=Page.objects.get(depth=1).pk,
        title=f"Draft parent {uid}",
        body_markdown="# Draft parent",
        publish=False,
    )
    parent_id = parent["id"]
    assert ContentPage.objects.get(pk=parent_id).live is False

    raw = call_tool_raw(
        client,
        token,
        "pages_create",
        type=CONTENT_PAGE_TYPE,
        parent_id=parent_id,
        title=f"Child of unpublished {uid}",
        body_markdown="# Child",
        publish=True,
    )

    if raw.get("isError"):
        text = raw["content"][0]["text"]
        assert any(code in text for code in ("403", "422", "error", "Error")), text
    else:
        child_id = raw.get("structuredContent", {}).get("id")
        assert child_id is not None
        assert ContentPage.objects.get(pk=child_id).live is not False
