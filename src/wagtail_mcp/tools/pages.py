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
    _register_page_action_tools(server)


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
        description="Delete a page permanently. Irreversible; use carefully. "
        "`pages_actions_delete` is the same delete action exposed under the "
        "REST `/actions/delete/` path for parity; both permanently delete the "
        "page and (per Wagtail semantics) its descendants. Prefer this tool. "
        'Returns `{"deleted": true, "page_id": ...}`.',
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


def _register_page_action_tools(server):
    """Register the page workflow/action tools (publish, move, copy, revert,
    aliases, translations) and the revision read tools."""

    @wagtail_tool(
        server,
        name="pages_actions_publish",
        annotations=WRITE,
        description="Publish a page's latest revision (creating a new one from "
        "the current draft state if none exists yet). Requires publish "
        "permission. Returns the published page detail.",
    )
    def pages_actions_publish(page_id: int) -> dict[str, object]:
        return trim_data(
            dispatch.call_operation(
                "pages_actions_publish", path_params={"page_id": page_id}
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_unpublish",
        annotations=DESTRUCTIVE,
        description="Unpublish a live page, taking it offline. Pass "
        "`recursive=True` to also unpublish its descendants. Requires publish "
        "permission. Note this is NOT idempotent: unpublishing an already-"
        'unpublished page errors with 403, so check `pages_detail(version="live")` '
        "first if unsure of the page's state. Returns the page detail.",
    )
    def pages_actions_unpublish(
        page_id: int, recursive: bool = False
    ) -> dict[str, object]:
        return trim_data(
            dispatch.call_operation(
                "pages_actions_unpublish",
                path_params={"page_id": page_id},
                body={"recursive": recursive},
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_copy",
        annotations=WRITE,
        description="Copy a page (and, with `recursive`, its subtree) to "
        "`destination_id` (a page id; omit to copy in place). `keep_live` "
        "controls whether the copy is published. `slug`/`title` override the "
        "copied values. Requires add permission. Returns the new page detail.",
    )
    def pages_actions_copy(
        page_id: int,
        destination_id: int | None = None,
        recursive: bool = False,
        keep_live: bool = True,
        slug: str | None = None,
        title: str | None = None,
    ) -> dict[str, object]:
        body: dict = {"recursive": recursive, "keep_live": keep_live}
        if destination_id is not None:
            body["destination_id"] = destination_id
        if slug is not None:
            body["slug"] = slug
        if title is not None:
            body["title"] = title
        return trim_data(
            dispatch.call_operation(
                "pages_actions_copy", path_params={"page_id": page_id}, body=body
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_move",
        annotations=WRITE,
        description="Move a page relative to `destination_id`. `position` "
        "controls placement: pass 'first-child' or 'last-child' to move the "
        "page UNDER `destination_id` as a child; 'left', 'right', 'first-sibling' "
        "or 'last-sibling' to move it as a sibling of `destination_id` (its parent "
        "becomes the destination's own parent). Without a child position the page "
        "becomes a sibling. Requires change permission. Returns the page detail.",
    )
    def pages_actions_move(
        page_id: int, destination_id: int, position: str | None = None
    ) -> dict[str, object]:
        body: dict = {"destination_id": destination_id}
        if position is not None:
            body["position"] = position
        return trim_data(
            dispatch.call_operation(
                "pages_actions_move", path_params={"page_id": page_id}, body=body
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_revert",
        annotations=WRITE,
        description="Revert a page to an earlier revision, replacing the current "
        "content with that revision's and creating a new revision. `revision_id` "
        "comes from `pages_revisions_list`. Requires change permission. Returns "
        "the reverted page detail.",
    )
    def pages_actions_revert(page_id: int, revision_id: int) -> dict[str, object]:
        return trim_data(
            dispatch.call_operation(
                "pages_actions_revert",
                path_params={"page_id": page_id},
                body={"revision_id": revision_id},
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_convert_alias",
        annotations=WRITE,
        description="Convert an alias page (created by `pages_actions_create_alias`) "
        "into a regular, independent page. Irreversible distinction from the "
        "aliased page. Requires change permission. Returns the converted page "
        "detail.",
    )
    def pages_actions_convert_alias(page_id: int) -> dict[str, object]:
        return trim_data(
            dispatch.call_operation(
                "pages_actions_convert_alias", path_params={"page_id": page_id}
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_create_alias",
        annotations=WRITE,
        description="Create an alias of a published page (`page_id`), which "
        "mirrors the original's content until converted. `destination_id` "
        "places the alias (omit for the same parent); `recursive` aliases the "
        "subtree. Requires add permission. Returns the new alias page detail.",
    )
    def pages_actions_create_alias(
        page_id: int,
        destination_id: int | None = None,
        recursive: bool = False,
        slug: str | None = None,
    ) -> dict[str, object]:
        body: dict = {"recursive": recursive}
        if destination_id is not None:
            body["destination_id"] = destination_id
        if slug is not None:
            body["slug"] = slug
        return trim_data(
            dispatch.call_operation(
                "pages_actions_create_alias",
                path_params={"page_id": page_id},
                body=body,
            )
        )

    @wagtail_tool(
        server,
        name="pages_actions_copy_for_translation",
        annotations=WRITE,
        description="Copy a page for translation into another `locale` (a "
        "language code string, e.g. 'fr'). `copy_parents` also translates "
        "untranslated ancestors; `recursive` covers the subtree; `alias` creates "
        "aliases instead of copies. Requires add permission. Returns the new "
        "translated page detail.",
    )
    def pages_actions_copy_for_translation(
        page_id: int,
        locale: str,
        copy_parents: bool = False,
        alias: bool = False,
        recursive: bool = False,
    ) -> dict[str, object]:
        return trim_data(
            dispatch.call_operation(
                "pages_actions_copy_for_translation",
                path_params={"page_id": page_id},
                body={
                    "locale": locale,
                    "copy_parents": copy_parents,
                    "alias": alias,
                    "recursive": recursive,
                },
            )
        )

    @wagtail_tool(
        server,
        name="pages_revisions_list",
        annotations=READ_ONLY,
        description="List a page's revisions (most recent first), each with id, "
        "created_at, and object_str. Use the ids here with `pages_actions_revert` "
        "and `pages_revisions_detail`. Paginated via `limit`/`offset`.",
    )
    def pages_revisions_list(
        page_id: int, limit: int = 20, offset: int = 0
    ) -> dict[str, object]:
        data = dispatch.call_operation(
            "pages_revisions_list",
            path_params={"page_id": page_id},
            query={"limit": limit, "offset": offset},
        )
        return {
            "count": data.get("count", len(data.get("items", []))),
            "items": [trim_revision(item) for item in data.get("items", [])],
        }

    @wagtail_tool(
        server,
        name="pages_revisions_detail",
        annotations=READ_ONLY,
        description="Get one revision's detail, including the full content "
        "snapshot (`content_object`) at that point in time. Use with "
        "`pages_actions_revert` to inspect before reverting.",
    )
    def pages_revisions_detail(page_id: int, revision_id: int) -> dict[str, object]:
        data = dispatch.call_operation(
            "pages_revisions_detail",
            path_params={"page_id": page_id, "revision_id": revision_id},
        )
        trimmed = trim_revision(data)
        content_object = data.get("content_object")
        if isinstance(content_object, dict):
            trimmed["content_object"] = trim_data(content_object)
        return trimmed


_REVISION_KEEP = (
    "id",
    "object_id",
    "created_at",
    "user_id",
    "object_str",
    "approved_go_live_at",
)


def trim_revision(item: dict) -> dict:
    """Trim a RevisionSchema item to the fields an agent needs."""
    return {k: v for k, v in item.items() if k in _REVISION_KEEP}
