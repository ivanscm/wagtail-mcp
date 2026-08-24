"""Redirect tools for the Wagtail v3 API.

Thin wrappers over ``dispatch.call_operation`` that flatten create/update
arguments and shape redirect responses for agents. Redirects wrap ``redirect``
(old path → target) and sit on ``wagtail.contrib.redirects``; reads are public
in the v3 API while writes require a bearer token with ``add``/``change``/
``delete`` permission. All auth/permissions live in the v3 API (dispatch
forwards the bearer token).
"""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    wagtail_tool,
)


#: Flat response fields (RedirectSchema has no ``meta`` block) worth surfacing.
REDIRECT_FIELDS = (
    "id",
    "old_path",
    "site_id",
    "is_permanent",
    "redirect_page_id",
    "redirect_page_route_path",
    "redirect_link",
    "automatically_created",
)


def _trim_redirect(data):
    """Reduce a redirect dict to its flat scalar fields."""
    return {key: data[key] for key in REDIRECT_FIELDS if key in data}


def _redirect_list(data, limit, offset):
    """Shape a paginated redirect response like ``shape_list`` but for flat items."""
    items = [_trim_redirect(item) for item in data.get("items", [])]
    count = data.get("count", len(items))
    next_offset = None
    if limit is not None and count > offset + len(items):
        next_offset = offset + len(items)
    return {"count": count, "next_offset": next_offset, "items": items}


def register(server):
    @wagtail_tool(
        server,
        name="redirects_list",
        annotations=READ_ONLY,
        description="List every redirect: old path, permanence, and target. "
        "Results are paginated: pass `limit`/`offset` and use "
        "``next_offset``` from the response to get the next page.",
    )
    def redirects_list(limit: int = 20, offset: int = 0) -> dict[str, object]:
        data = dispatch.call_operation(
            "redirects_list", query={"limit": limit, "offset": offset}
        )
        return _redirect_list(data, limit, offset)

    @wagtail_tool(
        server,
        name="redirects_find",
        annotations=READ_ONLY,
        description="Find the redirect for a given old path (e.g. "
        "'/old-page/'), returning the matching redirect's detail. Returns a "
        "404 error when no redirect matches the path.",
    )
    def redirects_find(old_path: str) -> dict[str, object]:
        data = dispatch.call_operation("redirects_find", query={"html_path": old_path})
        return _trim_redirect(data)

    @wagtail_tool(
        server,
        name="redirects_detail",
        annotations=READ_ONLY,
        description="Get one redirect's detail by id (from `redirects_list` / "
        "`redirects_find`): the old path, whether it is permanent, and its "
        "target (page id or external URL).",
    )
    def redirects_detail(redirect_id: int) -> dict[str, object]:
        data = dispatch.call_operation(
            "redirects_detail", path_params={"redirect_id": redirect_id}
        )
        return _trim_redirect(data)

    @wagtail_tool(
        server,
        name="redirects_create",
        annotations=WRITE,
        description="Create a redirect from `old_path` (a path like "
        "'/old-page/') to either a page (`redirect_page_id`) or a full URL "
        "(`redirect_link`). Provide `site_id` to scope it to one site "
        "(optional, applies to all sites when omitted). `is_permanent` marks "
        "a 301 vs 302. Returns the created redirect's detail.",
    )
    def redirects_create(
        old_path: str,
        redirect_page_id: int | None = None,
        redirect_link: str | None = None,
        site_id: int | None = None,
        is_permanent: bool = True,
    ) -> dict[str, object]:
        body = {"old_path": old_path, "is_permanent": is_permanent}
        if redirect_page_id is not None:
            body["redirect_page_id"] = redirect_page_id
        if redirect_link is not None:
            body["redirect_link"] = redirect_link
        if site_id is not None:
            body["site"] = site_id
        data = dispatch.call_operation("redirects_create", body=body)
        return _trim_redirect(data)

    @wagtail_tool(
        server,
        name="redirects_update",
        annotations=WRITE,
        description="Update an existing redirect (by `redirect_id`) — its old "
        "path, site scope, or permanence. Only the fields you pass are "
        "changed; the existing link/page target is preserved unless you "
        "supply a new one. Pass `redirect_page_id` to point at a page, or "
        "`redirect_link` to point at a URL — giving one clears the other "
        "(switch target type). Returns the updated redirect's detail.",
    )
    def redirects_update(
        redirect_id: int,
        old_path: str | None = None,
        redirect_page_id: int | None = None,
        redirect_link: str | None = None,
        site_id: int | None = None,
        is_permanent: bool | None = None,
    ) -> dict[str, object]:
        # The v3 ``redirects_update`` schema requires only ``old_path`; the
        # target fields are optional (defaulting to null/empty). Fetch the
        # current redirect and merge so that a partial update preserves the
        # existing target instead of silently clearing it.
        current = dispatch.call_operation(
            "redirects_detail", path_params={"redirect_id": redirect_id}
        )
        update_body = {
            "old_path": old_path if old_path is not None else current["old_path"],
            "is_permanent": (
                is_permanent if is_permanent is not None else current["is_permanent"]
            ),
        }
        if site_id is not None:
            update_body["site"] = site_id
        elif current["site_id"] is not None:
            update_body["site"] = current["site_id"]

        if redirect_page_id is not None:
            # Switch / keep to a page target: clear any external link.
            update_body["redirect_page_id"] = redirect_page_id
            update_body["redirect_link"] = ""
            if current.get("redirect_page_route_path"):
                update_body["redirect_page_route_path"] = current[
                    "redirect_page_route_path"
                ]
        elif redirect_link is not None:
            # Switch / keep to an external link: clear any page target.
            update_body["redirect_page_id"] = None
            update_body["redirect_link"] = redirect_link
        else:
            # No target change: preserve the existing target unchanged.
            update_body["redirect_page_id"] = current.get("redirect_page_id")
            update_body["redirect_link"] = current.get("redirect_link")
        data = dispatch.call_operation(
            "redirects_update",
            path_params={"redirect_id": redirect_id},
            body=update_body,
        )
        return _trim_redirect(data)

    @wagtail_tool(
        server,
        name="redirects_delete",
        annotations=DESTRUCTIVE,
        description="Delete a redirect permanently by id. Irreversible; use "
        "carefully. Returns `{'deleted': true, 'redirect_id': ...}`.",
    )
    def redirects_delete(redirect_id: int) -> dict[str, object]:
        dispatch.call_operation(
            "redirects_delete", path_params={"redirect_id": redirect_id}
        )
        return {"deleted": True, "redirect_id": redirect_id}
