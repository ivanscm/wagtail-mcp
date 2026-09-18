import base64
import binascii
import functools

from django.conf import settings
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from wagtail_mcp.errors import APIError, format_api_error


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)
WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


def wagtail_tool(server, *, name, description, annotations):
    """Register ``fn`` as an MCP tool, translating APIError into a ToolError.

    Curated tools are thin: they map tool arguments to v3 operation payloads via
    ``dispatch.call_operation``, then shape the response for agents.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except APIError as err:
                raise ToolError(format_api_error(err)) from err

        return server.tool(name=name, description=description, annotations=annotations)(
            wrapper
        )

    return decorator


def max_limit_hint() -> str:
    """Sentence for paginated tool descriptions stating the v3 max ``limit``.

    The v3 API rejects ``limit`` above ``WAGTAILAPI_LIMIT_MAX`` (default 20)
    with a 400 ("limit cannot be higher than 20"), which agents otherwise
    discover by failing a call; stating the cap in the description prevents
    that. Read at tool-registration time so the descriptions match the
    project's current setting. ``WAGTAILAPI_LIMIT_MAX = None`` disables the cap.
    """
    limit_max = getattr(settings, "WAGTAILAPI_LIMIT_MAX", 20)
    if limit_max is None:
        return "`limit` has no maximum."
    return f"Maximum `limit` is {limit_max} (`WAGTAILAPI_LIMIT_MAX`)."


def trim(item, meta_keys):
    """Reduce a v3 item dict to ``id``/title-ish keys plus a whitelisted ``meta``."""
    result = {
        k: v
        for k, v in item.items()
        if k in ("id", "title", "name", "label", "language_code")
    }
    meta = item.get("meta")
    if isinstance(meta, dict):
        filtered = {k: v for k, v in meta.items() if k in meta_keys}
        result = {k: v for k, v in result.items() if k != "title" or v is not None}
        result["meta"] = filtered
        if "title" in meta and "title" not in result:
            result["title"] = meta["title"]
    return result


def shape_list(data, meta_keys, limit=None, offset=0):
    """Shape a v3 paginated response into ``{count, next_offset, items}``."""
    items = [trim(item, meta_keys) for item in data.get("items", [])]
    count = data.get("count", data.get("meta", {}).get("total_count", len(items)))
    next_offset = None
    if limit is not None and count > offset + len(items):
        next_offset = offset + len(items)
    return {"count": count, "next_offset": next_offset, "items": items}


#: Suffix → MIME type for uploads whose ``content_type`` is not supplied.
#: Covers the image/document formats Wagtail's upload forms accept; anything
#: else must be supplied explicitly by the caller.
_EXTENSION_CONTENT_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".json": "application/json",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def decode_upload(content_base64: str, filename: str, content_type: str | None = None):
    """Decode a base64-encoded upload into ``(filename, bytes, content_type)``.

    Validates that ``content_base64`` is well-formed, so a client sending a
    corrupt payload gets a helpful error rather than a ``binascii`` traceback
    mid-tool. When ``content_type`` is omitted it is inferred from ``filename``'s
    extension; raises ``ToolError`` if the suffix is not recognised.
    """
    try:
        payload = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolError(
            f"content_base64 is not valid base64: {exc}"
            " — send the file contents encoded as base64 (not a URL or path)."
        ) from exc

    if content_type is None:
        ext = _suffix(filename)
        content_type = _EXTENSION_CONTENT_TYPES.get(ext)
        if content_type is None:
            raise ToolError(
                f"Could not infer a content type from filename {filename!r}. "
                "Pass `content_type` explicitly, or use a recognised extension "
                "such as .png, .jpg, .pdf or .txt."
            )
    return filename, payload, content_type


def _suffix(filename: str) -> str:
    """Return the lowercase extension of ``filename`` including the dot."""
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


def _is_collection_required_error(err: APIError) -> bool:
    """Whether an ``APIError`` is the v3 'collection is required' 422.

    Projects with multiple Collections require an explicit ``collection_id`` on
    image/document uploads; ``build_image_form``/``build_document_form`` mark the
    ``collection`` field required. When only the Root collection exists the
    field is hidden/optional, so a bare upload succeeds there. We detect this
    error to trigger the root-collection fallback.
    """
    if err.status != 422:
        return False
    for item in err.problem.get("errors") or []:
        loc = item.get("loc") or []
        if "collection" in loc and item.get("type") == "required":
            return True
    return False


def _root_collection_id():
    """Return the id of the project's root collection for the media type.

    The v3 API does not expose Collections (only ``ImageCreateSchema``/"
    ``DocumentCreateSchema`` accept a ``collection_id`` form field), so we read
    the migration-seeded root collection directly via the ORM. This is the
    per-project default Wagtail's own upload forms fall back to.
    """
    from wagtail.models import Collection

    return Collection.get_first_root_node().id


def perform_upload(
    dispatch,
    operation_id: str,
    *,
    title: str,
    filename: str,
    payload: bytes,
    mime: str,
    description: str | None = None,
    collection_id: int | None = None,
) -> dict | None:
    """Dispatch a media upload, adding a root-collection fallback.

    ``operation_id`` is ``images_create`` or ``documents_create``. When
    ``collection_id`` is given it is passed through to the v3 form. When
    omitted we first try without it; if the API replies 422 specifically
    because ``collection`` is required (a project with multiple collections),
    we retry once with the root collection so a naive call still succeeds.

    ``dispatch`` is the ``wagtail_mcp.dispatch`` module (injected so the tool
    modules own their imports and tests can mock ``dispatch._client``).
    """
    form: dict = {"title": title}
    if description is not None:
        form["description"] = description
    if collection_id is not None:
        form["collection_id"] = collection_id
    files = {"file": (filename, payload, mime)}
    try:
        return dispatch.call_operation(operation_id, form=form, files=files)
    except APIError as err:
        if collection_id is None and _is_collection_required_error(err):
            form["collection_id"] = _root_collection_id()
            return dispatch.call_operation(operation_id, form=form, files=files)
        raise
