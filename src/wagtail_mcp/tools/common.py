import base64
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


def decode_upload(content_base64: str, filename: str, content_type: str):
    """Decode a base64-encoded upload into ``(filename, bytes, content_type)``."""
    return filename, base64.b64decode(content_base64), content_type
