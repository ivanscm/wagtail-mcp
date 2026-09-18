"""Image tools for the Wagtail v3 API.

Thin wrappers over ``dispatch.call_operation`` that flatten create/update
arguments and shape image responses for agents. Uploads arrive as base64 and
are decoded + MIME-typed by ``tools.common.decode_upload``. All auth/permissions
live in the v3 API (dispatch forwards the bearer token).
"""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    decode_upload,
    max_limit_hint,
    perform_upload,
    shape_detail,
    shape_list,
    wagtail_tool,
)


#: Image *list* item ``meta`` keys worth surfacing to an agent. Detail
#: responses are passed through untrimmed (see ``shape_detail``).
IMAGE_META_KEYS = ("type", "detail_url", "download_url", "tags")


def register(server):
    @wagtail_tool(
        server,
        name="images_list",
        annotations=READ_ONLY,
        description="List images, optionally filtered by `search` (matches "
        "title). Results are paginated: pass `limit`/`offset` and use "
        "``next_offset``` from the response to get the next page. "
        f"{max_limit_hint()}",
    )
    def images_list(
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        query = {"limit": limit, "offset": offset}
        if search is not None:
            query["search"] = search
        data = dispatch.call_operation("images_list", query=query)
        return shape_list(data, IMAGE_META_KEYS, limit=limit, offset=offset)

    @wagtail_tool(
        server,
        name="images_detail",
        annotations=READ_ONLY,
        description="Get one image's detail: dimensions, description, focal "
        "point, collection, and URLs (``detail_url`` and ``download_url``). "
        "Use the id from `images_list`. Rich metadata (tags) is exposed "
        "under ``meta``.",
    )
    def images_detail(image_id: int) -> dict[str, object]:
        data = dispatch.call_operation(
            "images_detail", path_params={"image_id": image_id}
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="images_create",
        annotations=WRITE,
        description="Upload a new image. Provide the raw file bytes as base64 in "
        "`content_base64` (the base64 string of the file contents), plus a "
        "`filename`; `content_type` is inferred from the filename's extension "
        "(e.g. .png/.jpg/.gif/.webp) when omitted, or pass it directly. "
        "`title` labels the image; `description` is optional alt-text/caption "
        "metadata. `collection_id` optionally picks a specific "
        "Collection; when omitted the project's default/root collection is used "
        "automatically. Returns the created image's detail (including its "
        "`download_url`).",
    )
    def images_create(
        title: str,
        content_base64: str,
        filename: str,
        description: str | None = None,
        content_type: str | None = None,
        collection_id: int | None = None,
    ) -> dict[str, object]:
        _, payload, mime = decode_upload(content_base64, filename, content_type)
        data = perform_upload(
            dispatch,
            "images_create",
            title=title,
            filename=filename,
            payload=payload,
            mime=mime,
            description=description,
            collection_id=collection_id,
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="images_update",
        annotations=WRITE,
        description="Update an existing image's title and/or description. "
        "Only the fields you pass are changed (PATCH semantics via the v3 "
        "API). Requires the image's id from `images_list`/`images_detail`. "
        "Returns the updated image detail.",
    )
    def images_update(
        image_id: int,
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, object]:
        body = {
            key: value
            for key, value in {"title": title, "description": description}.items()
            if value is not None
        }
        data = dispatch.call_operation(
            "images_update",
            path_params={"image_id": image_id},
            body=body,
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="images_delete",
        annotations=DESTRUCTIVE,
        description="Delete an image permanently. Irreversible; use carefully. "
        'Returns `{"deleted": true, "image_id": ...}`.',
    )
    def images_delete(image_id: int) -> dict[str, object]:
        dispatch.call_operation("images_delete", path_params={"image_id": image_id})
        return {"deleted": True, "image_id": image_id}
