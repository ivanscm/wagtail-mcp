"""Site tools. See docs/tools.md."""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    max_limit_hint,
    shape_detail,
    wagtail_tool,
)


# List-item fields retained for sites (no ``meta`` block).
SITE_FIELDS = (
    "id",
    "hostname",
    "port",
    "site_name",
    "root_page_id",
    "is_default_site",
)


def _trim_site(data):
    """Trim a site *list* item to the whitelisted fields."""
    return {key: data[key] for key in SITE_FIELDS if key in data}


def _site_list(data, limit, offset):
    items = [_trim_site(item) for item in data.get("items", [])]
    count = data.get("count", len(items))
    next_offset = None
    if limit is not None and count > offset + len(items):
        next_offset = offset + len(items)
    return {"count": count, "next_offset": next_offset, "items": items}


def register(server):
    @wagtail_tool(
        server,
        name="sites_list",
        annotations=READ_ONLY,
        description="List the sites in this Wagtail project: hostname, port, "
        "site name, and their root page. Results are paginated: pass "
        "`limit`/`offset` and use ``next_offset``` from the response for the "
        "next page. "
        f"{max_limit_hint()}",
    )
    def sites_list(limit: int = 20, offset: int = 0) -> dict[str, object]:
        data = dispatch.call_operation(
            "sites_list", query={"limit": limit, "offset": offset}
        )
        return _site_list(data, limit, offset)

    @wagtail_tool(
        server,
        name="sites_detail",
        annotations=READ_ONLY,
        description="Get one site's detail by id (from `sites_list`): "
        "hostname, port, site name, root page id, and default-site flag.",
    )
    def sites_detail(site_id: int) -> dict[str, object]:
        data = dispatch.call_operation("sites_detail", path_params={"site_id": site_id})
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="sites_create",
        annotations=WRITE,
        description="Create a new site on an existing root page "
        "(`root_page_id` — find it via `pages_list`). `hostname` is required, "
        "`port` defaults to 80, `site_name` is optional. Use "
        "`is_default_site=True` to make it the default site. Returns the "
        "created site's detail.",
    )
    def sites_create(
        hostname: str,
        root_page_id: int,
        port: int = 80,
        site_name: str = "",
        is_default_site: bool = False,
    ) -> dict[str, object]:
        body = {
            "hostname": hostname,
            "root_page_id": root_page_id,
            "port": port,
            "site_name": site_name,
            "is_default_site": is_default_site,
        }
        data = dispatch.call_operation("sites_create", body=body)
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="sites_update",
        annotations=WRITE,
        description="Update an existing site (by `site_id`): its hostname, "
        "port, site name, root page, or default-site flag. Only the fields "
        "you pass are changed. Returns the updated site's detail.",
    )
    def sites_update(
        site_id: int,
        hostname: str | None = None,
        root_page_id: int | None = None,
        port: int | None = None,
        site_name: str | None = None,
        is_default_site: bool | None = None,
    ) -> dict[str, object]:
        # v3 requires a full body; merge unchanged fields for PATCH semantics.
        current = dispatch.call_operation(
            "sites_detail", path_params={"site_id": site_id}
        )
        body = {
            "hostname": hostname if hostname is not None else current["hostname"],
            "root_page_id": (
                root_page_id if root_page_id is not None else current["root_page_id"]
            ),
            "port": port if port is not None else current["port"],
            "site_name": site_name if site_name is not None else current["site_name"],
            "is_default_site": (
                is_default_site
                if is_default_site is not None
                else current["is_default_site"]
            ),
        }
        data = dispatch.call_operation(
            "sites_update", path_params={"site_id": site_id}, body=body
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="sites_delete",
        annotations=DESTRUCTIVE,
        description="Delete a site permanently by id. Irreversible; use "
        "carefully. Returns `{'deleted': true, 'site_id': ...}`.",
    )
    def sites_delete(site_id: int) -> dict[str, object]:
        dispatch.call_operation("sites_delete", path_params={"site_id": site_id})
        return {"deleted": True, "site_id": site_id}
