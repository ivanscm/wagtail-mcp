import base64
import binascii
import functools

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
