"""Document tools for the Wagtail v3 API.

Thin wrappers over ``dispatch.call_operation`` that flatten create/update
arguments and shape document responses for agents. Uploads arrive as base64
and are decoded + MIME-typed by ``tools.common.decode_upload``.
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


#: Document *list* item ``meta`` keys worth surfacing to an agent. Detail
#: responses are passed through untrimmed (see ``shape_detail``).
DOCUMENT_META_KEYS = ("type", "detail_url", "download_url", "tags")


def register(server):
    @wagtail_tool(
        server,
        name="documents_list",
        annotations=READ_ONLY,
        description="List documents, optionally filtered by `search` (matches "
        "title). Results are paginated: pass `limit`/`offset` and use "
        "``next_offset``` from the response to get the next page. "
        f"{max_limit_hint()}",
    )
    def documents_list(
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        query = {"limit": limit, "offset": offset}
        if search is not None:
            query["search"] = search
        data = dispatch.call_operation("documents_list", query=query)
        return shape_list(data, DOCUMENT_META_KEYS, limit=limit, offset=offset)

    @wagtail_tool(
        server,
        name="documents_detail",
        annotations=READ_ONLY,
        description="Get one document's detail: title, collection, and URLs "
        "(``detail_url`` and ``download_url``). Use the id from "
        "`documents_list`. Rich metadata (tags) is exposed under ``meta``.",
    )
    def documents_detail(document_id: int) -> dict[str, object]:
        data = dispatch.call_operation(
            "documents_detail", path_params={"document_id": document_id}
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="documents_create",
        annotations=WRITE,
        description="Upload a new document. Provide the raw file bytes as base64 "
        "in `content_base64` (the base64 string of the file contents), plus a "
        "`filename`; `content_type` is inferred from the filename's extension "
        "(e.g. .pdf/.txt/.md) when omitted, or pass it directly. `title` labels "
        "the document. `collection_id` optionally picks a specific Collection; "
        "when omitted the project's default/root collection is used "
        "automatically. Returns the created document's detail (including its "
        "`download_url`).",
    )
    def documents_create(
        title: str,
        content_base64: str,
        filename: str,
        content_type: str | None = None,
        collection_id: int | None = None,
    ) -> dict[str, object]:
        _, payload, mime = decode_upload(content_base64, filename, content_type)
        data = perform_upload(
            dispatch,
            "documents_create",
            title=title,
            filename=filename,
            payload=payload,
            mime=mime,
            collection_id=collection_id,
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="documents_update",
        annotations=WRITE,
        description="Update an existing document's title. Only the fields you "
        "pass are changed (PATCH semantics via the v3 API). Requires the "
        "document's id from `documents_list`/`documents_detail`. Returns the "
        "updated document detail.",
    )
    def documents_update(document_id: int, title: str) -> dict[str, object]:
        data = dispatch.call_operation(
            "documents_update",
            path_params={"document_id": document_id},
            body={"title": title},
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="documents_delete",
        annotations=DESTRUCTIVE,
        description="Delete a document permanently. Irreversible; use "
        'carefully. Returns `{"deleted": true, "document_id": ...}`.',
    )
    def documents_delete(document_id: int) -> dict[str, object]:
        dispatch.call_operation(
            "documents_delete", path_params={"document_id": document_id}
        )
        return {"deleted": True, "document_id": document_id}
