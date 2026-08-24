"""Page tools for the Wagtail v3 API.

Thin wrappers over ``dispatch.call_operation`` that flatten read/write
arguments and shape responses for agents. Rely on the v3 API for auth and
permissions (``dispatch`` forwards the bearer token); these tools only
translate arguments and responses.
"""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    shape_list,
    trim,
    wagtail_tool,
)


# Page meta keys worth exposing to an agent from a page list item.
PAGE_LIST_META_KEYS = ("type", "slug", "locale", "html_url", "first_published_at")
# Detail responses carry more context worth keeping.
PAGE_DETAIL_META_KEYS = (
    "type",
    "slug",
    "locale",
    "html_url",
    "parent",
    "show_in_menus",
    "first_published_at",
)


def register(server):
    @wagtail_tool(
        server,
        name="pages_list",
        annotations=READ_ONLY,
        description="List pages, optionally filtered. `child_of` (page id or "
        "'root') or `descendant_of` restricts to a branch; `search` does a "
        "full-text search. Results are paginated: pass `limit`/`offset` and use "
        "```next_offset``` from the response to get the next page.",
    )
    def pages_list(
        child_of: int | str | None = None,
        descendant_of: int | str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        query = {"limit": limit, "offset": offset}
        if child_of is not None:
            query["child_of"] = "root" if child_of == "root" else child_of
        if descendant_of is not None:
            query["descendant_of"] = (
                "root" if descendant_of == "root" else descendant_of
            )
        if search is not None:
            query["search"] = search
        data = dispatch.call_operation("pages_list", query=query)
        return shape_list(data, PAGE_LIST_META_KEYS, limit=limit, offset=offset)

    @wagtail_tool(
        server,
        name="pages_find",
        annotations=READ_ONLY,
        description="Find a page by its URL path (e.g. 'blog/my-post/') and "
        "return its detail. Pass `site` as the site hostname (optionally "
        "':port') when the page is not on the default site. The v3 API "
        "redirects to the page detail; this tool follows it.",
    )
    def pages_find(html_path: str, site: str | None = None) -> dict[str, object]:
        query = {"html_path": html_path}
        if site is not None:
            query["site"] = site
        data = dispatch.call_operation("pages_find", query=query)
        return trim_data(data)

    @wagtail_tool(
        server,
        name="pages_detail",
        annotations=READ_ONLY,
        description="Get one page's detail. `version` is 'live' (published) or "
        "'draft' (latest revision). Rich text fields are returned as Markdown "
        "by default; set `rich_text_format` to 'html' to get HTML instead. "
        "Use `schema_detail` first to learn a type's fields.",
    )
    def pages_detail(
        page_id: int,
        version: str = "live",
        rich_text_format: str | None = "markdown",
    ) -> dict[str, object]:
        query = {"version": version}
        if rich_text_format is not None:
            query["rich_text_format"] = rich_text_format
        data = dispatch.call_operation(
            "pages_detail", path_params={"page_id": page_id}, query=query
        )
        return trim_data(data)

    _register_page_write_tools(server)


def trim_data(data):
    """Trim a page detail response to the atomic fields + whitelisted meta."""
    result = {k: v for k, v in data.items() if not k.startswith("meta")}
    result["meta"] = trim(data, PAGE_DETAIL_META_KEYS)["meta"]
    return result


def _markdown_body(body_markdown: str | None) -> dict | None:
    """Encode a Markdown rich-text body for a write payload.

    Wagtail's v3 rich-text *write* input accepts either a plain string (DB
    HTML) or an envelope object selecting the input format. Sending Markdown
    requires the envelope ``{"format": "db_markdown", "content": ...}``; the
    ``rich_text_format`` query parameter only affects read responses (the
    write schema never reads it). ``None``/empty means the field is omitted
    so a page type without a body field is not rejected.
    """
    if not body_markdown:
        return None
    return {"format": "db_markdown", "content": body_markdown}


def _register_page_write_tools(server):
    """Register the page write and destructive tools onto ``server``.

    Called from ``register`` so all page tools register in one pass.
    """

    @wagtail_tool(
        server,
        name="pages_create",
        annotations=WRITE,
        description="Create a page as a draft (unless `publish` is true). "
        "`type` is the content type label (e.g. 'app_label.ModelName'); call "
        "`schema_detail` first for the type's fields. Markdown in "
        "`body_markdown` is converted server-side. `parent_id` must be an "
        "existing page id (see `pages_list`/`pages_find`). Returns the "
        "created page detail.",
    )
    def pages_create(
        type: str,
        parent_id: int,
        title: str,
        body_markdown: str = "",
        publish: bool = False,
        slug: str | None = None,
    ) -> dict[str, object]:
        meta = {"type": type, "parent_id": parent_id}
        if publish:
            meta["action"] = "publish"
        body = {"meta": meta, "title": title}
        if slug is not None:
            body["slug"] = slug
        markdown = _markdown_body(body_markdown)
        if markdown is not None:
            body["body"] = markdown
        data = dispatch.call_operation("pages_create", body=body)
        return trim_data(data)

    @wagtail_tool(
        server,
        name="pages_update",
        annotations=WRITE,
        description="Update an existing page. Only the fields you pass are "
        "changed (PATCH semantics). `body_markdown` is Markdown, converted "
        "server-side. Pass `publish=True` to publish; otherwise the change "
        "is saved as a draft revision, leaving the live page untouched. The "
        "page's content type is read from the page itself, so you only need "
        "its id. Returns the updated page detail.",
    )
    def pages_update(
        page_id: int,
        title: str | None = None,
        body_markdown: str | None = None,
        publish: bool | None = None,
    ) -> dict[str, object]:
        # Learn the page's own content type so the update envelope's
        # ``meta.type`` matches what v3's discriminated-union update schema
        # expects.
        current = dispatch.call_operation(
            "pages_detail", path_params={"page_id": page_id}, query={"version": "draft"}
        )
        meta = {"type": current["meta"]["type"]}
        if publish:
            meta["action"] = "publish"
        body: dict = {"meta": meta}
        if title is not None:
            body["title"] = title
        markdown = _markdown_body(body_markdown)
        if markdown is not None:
            body["body"] = markdown
        data = dispatch.call_operation(
            "pages_update",
            path_params={"page_id": page_id},
            body=body,
        )
        return trim_data(data)

    @wagtail_tool(
        server,
        name="pages_delete",
        annotations=DESTRUCTIVE,
        description="Delete a page permanently (and, by Wagtail semantics, "
        "its descendants in preview — see `pages_actions_delete` for the "
        "tree-scoped variant). Irreversible; use carefully. Returns "
        '`{"deleted": true, "page_id": ...}`.',
    )
    def pages_delete(page_id: int) -> dict[str, object]:
        dispatch.call_operation("pages_delete", path_params={"page_id": page_id})
        return {"deleted": True, "page_id": page_id}

    @wagtail_tool(
        server,
        name="pages_actions_delete",
        annotations=DESTRUCTIVE,
        description="Delete a page permanently via the actions endpoint. "
        "Irreversible; use carefully. This is the explicit `/actions/delete/` "
        "variant of `pages_delete`; on the Wagtail v3 API both call the same "
        "delete action, so prefer `pages_delete` and keep this for parity with "
        'the REST surface. Returns `{"deleted": true, "page_id": ...}`.',
    )
    def pages_actions_delete(page_id: int) -> dict[str, object]:
        dispatch.call_operation(
            "pages_actions_delete", path_params={"page_id": page_id}
        )
        return {"deleted": True, "page_id": page_id}
