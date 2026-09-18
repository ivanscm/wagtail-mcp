"""Locale tools for the Wagtail v3 API.

Thin wrappers over ``dispatch.call_operation`` that flatten create/update
arguments and shape locale responses for agents. Locales require a bearer
token. All auth/permissions live in the v3 API.
"""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    max_limit_hint,
    shape_detail,
    trim,
    wagtail_tool,
)


#: ``meta`` keys worth surfacing from a locale *list* item. LocaleSchema
#: extends ``BaseSchema`` so responses carry a ``meta`` block (type/warnings).
#: Detail responses are passed through untrimmed (see ``shape_detail``).
LOCALE_META_KEYS = ("type",)

#: Atomic locale response fields (outside ``meta``).
LOCALE_FIELDS = (
    "id",
    "language_code",
    "display_name",
    "is_bidi",
    "is_default",
)


def _trim_locale(data):
    """Reduce a locale *list* item to its atomic fields + whitelisted meta."""
    result = {key: data[key] for key in LOCALE_FIELDS if key in data}
    result["meta"] = trim(data, LOCALE_META_KEYS)["meta"]
    return result


def register(server):
    @wagtail_tool(
        server,
        name="locales_list",
        annotations=READ_ONLY,
        description="List the locales in this Wagtail project: language code, "
        "display name, and whether each is the default. Results are "
        "paginated: pass `limit`/`offset` and use ``next_offset``` from the "
        "response for the next page. "
        f"{max_limit_hint()}",
    )
    def locales_list(limit: int = 20, offset: int = 0) -> dict[str, object]:
        data = dispatch.call_operation(
            "locales_list", query={"limit": limit, "offset": offset}
        )
        items = [_trim_locale(item) for item in data.get("items", [])]
        count = data.get("count", len(items))
        next_offset = None
        if limit is not None and count > offset + len(items):
            next_offset = offset + len(items)
        return {"count": count, "next_offset": next_offset, "items": items}

    @wagtail_tool(
        server,
        name="locales_detail",
        annotations=READ_ONLY,
        description="Get one locale's detail by id (from `locales_list`): its "
        "language code, display name, bidirectional flag, and default flag.",
    )
    def locales_detail(locale_id: int) -> dict[str, object]:
        data = dispatch.call_operation(
            "locales_detail", path_params={"locale_id": locale_id}
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="locales_create",
        annotations=WRITE,
        description="Create a new locale for a language (e.g. 'fr', 'de', "
        "'es'). Returns the created locale's detail. Locales can be created "
        "for any language code Django/Wagtail supports.",
    )
    def locales_create(language_code: str) -> dict[str, object]:
        data = dispatch.call_operation(
            "locales_create", body={"language_code": language_code}
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="locales_update",
        annotations=WRITE,
        description="Update an existing locale's language code (by "
        "`locale_id`). Returns the updated locale's detail.",
    )
    def locales_update(locale_id: int, language_code: str) -> dict[str, object]:
        data = dispatch.call_operation(
            "locales_update",
            path_params={"locale_id": locale_id},
            body={"language_code": language_code},
        )
        return shape_detail(data)

    @wagtail_tool(
        server,
        name="locales_delete",
        annotations=DESTRUCTIVE,
        description="Delete a locale permanently by id. Irreversible; the v3 "
        "API refuses to delete the last remaining locale or one in use by "
        "pages/objects. Returns `{'deleted': true, 'locale_id': ...}`.",
    )
    def locales_delete(locale_id: int) -> dict[str, object]:
        dispatch.call_operation("locales_delete", path_params={"locale_id": locale_id})
        return {"deleted": True, "locale_id": locale_id}
