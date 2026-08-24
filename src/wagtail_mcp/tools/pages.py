"""Page read tools for the Wagtail v3 API.

Thin wrappers over ``dispatch.call_operation`` that flatten read arguments
and shape responses for agents. Rely on the v3 API for auth and permissions
(``dispatch`` forwards the bearer token); these tools only translate
arguments and responses.
"""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import READ_ONLY, shape_list, trim, wagtail_tool


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


def trim_data(data):
    """Trim a page detail response to the atomic fields + whitelisted meta."""
    result = {k: v for k, v in data.items() if not k.startswith("meta")}
    result["meta"] = trim(data, PAGE_DETAIL_META_KEYS)["meta"]
    return result
