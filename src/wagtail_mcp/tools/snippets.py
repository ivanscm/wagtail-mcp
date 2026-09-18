"""Generic snippet tools for the Wagtail v3 API.

Snippet endpoints are keyed by a ``type`` path parameter: the model label
(``app_label.ModelName``). Payload shapes are project-specific (they derive
from each snippet model's ``api_fields``), so create/update take an opaque
``data`` dict rather than typed arguments — the tool descriptions point the
agent at ``schema_detail`` to discover the writable fields for a given type.

Only snippet models with the relevant mixins expose the action/revision
endpoints these tools wrap: publish/unpublish need ``DraftStateMixin``,
revisions/revert need ``RevisionMixin``, and copy_for_translation needs
``TranslatableMixin`` (plus internationalization enabled). Calling an action
against an incompatible type returns a 422 from the API; we pass that through
rather than re-deriving the type capability matrix here.
"""

from wagtail_mcp import dispatch
from wagtail_mcp.tools.common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    max_limit_hint,
    shape_list,
    trim,
    wagtail_tool,
)


#: Meta keys worth keeping from snippet list/detail items. ``type`` and
#: ``detail_url`` are the only stable ones; the atomic fields differ per model
#: (captured by ``trim`` which keeps ``id``/``name``/``label`` etc.).
SNIPPET_META_KEYS = ("type", "detail_url")


def _type_param(type: str) -> dict:
    """Path params for a snippet endpoint, keyed by the URL's ``{type}``/``{pk}``."""
    return {"type": type}


def _trim_snippet(data: dict) -> dict:
    """Trim a single snippet detail response to atomic fields + whitelisted meta."""
    result = {k: v for k, v in data.items() if not k.startswith("meta")}
    result["meta"] = trim(data, SNIPPET_META_KEYS)["meta"]
    return result


def _payload(data: dict, publish: bool = False) -> dict:
    """Build a snippet create/update body.

    Snippet write schemas take the fields directly (the type is the URL path
    parameter, not part of the body). DraftStateMixin models additionally
    accept ``meta.action`` to publish in the same call.
    """
    body = dict(data)
    if publish:
        body["meta"] = {"action": "publish"}
    return body


def register(server):
    @wagtail_tool(
        server,
        name="snippets_list",
        annotations=READ_ONLY,
        description="List snippets of one `type` (a model label like "
        "'app_label.ModelName'). `search` does a partial text match; paginate "
        "with `limit`/`offset` and follow ```next_offset``` from the response. "
        "Call `schema_list` to discover the API-enabled snippet types. "
        f"{max_limit_hint()}",
    )
    def snippets_list(
        type: str,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        query = {"limit": limit, "offset": offset}
        if search is not None:
            query["search"] = search
        data = dispatch.call_operation(
            "snippets_list",
            path_params=_type_param(type),
            query=query,
        )
        return shape_list(data, SNIPPET_META_KEYS, limit=limit, offset=offset)

    @wagtail_tool(
        server,
        name="snippets_detail",
        annotations=READ_ONLY,
        description="Get one snippet's detail for `type` (a model label). "
        "`version` is 'live' (published) or 'draft' (latest revision; "
        "draftable model types only). Call `schema_list` first to discover the "
        "type's label.",
    )
    def snippets_detail(
        type: str, snippet_id: int, version: str = "live"
    ) -> dict[str, object]:
        data = dispatch.call_operation(
            "snippets_detail",
            path_params={**_type_param(type), "pk": snippet_id},
            query={"version": version},
        )
        return _trim_snippet(data)

    @wagtail_tool(
        server,
        name="snippets_create",
        annotations=WRITE,
        description="Create a snippet of `type` with the given `data` fields. "
        "`data`'s allowed keys are the type's writable API fields — call "
        "`schema_detail(type)` first to discover them. Pass `publish=True` to "
        "publish immediately (draftable model types only). Returns the created "
        "snippet detail.",
    )
    def snippets_create(
        type: str, data: dict, publish: bool = False
    ) -> dict[str, object]:
        created = dispatch.call_operation(
            "snippets_create",
            path_params=_type_param(type),
            body=_payload(data, publish),
        )
        return _trim_snippet(created)

    @wagtail_tool(
        server,
        name="snippets_update",
        annotations=WRITE,
        description="Update an existing snippet's fields. `data` is a partial "
        "(PATCH-style) body: only the keys you pass change; the allowed keys "
        "are the type's writable API fields (see `schema_detail(type)`). Pass "
        "`publish=True` to publish the result (draftable types). Returns the "
        "updated snippet detail.",
    )
    def snippets_update(
        type: str, snippet_id: int, data: dict, publish: bool = False
    ) -> dict[str, object]:
        updated = dispatch.call_operation(
            "snippets_update",
            path_params={**_type_param(type), "pk": snippet_id},
            body=_payload(data, publish),
        )
        return _trim_snippet(updated)

    @wagtail_tool(
        server,
        name="snippets_delete",
        annotations=DESTRUCTIVE,
        description="Permanently delete a snippet. Irreversible. "
        "`snippets_actions_delete` is the same delete action exposed under the "
        "REST `/actions/delete/` path for parity — prefer this tool. Returns "
        '`{"deleted": true, "type": ..., "snippet_id": ...}`.',
    )
    def snippets_delete(type: str, snippet_id: int) -> dict[str, object]:
        dispatch.call_operation(
            "snippets_delete",
            path_params={**_type_param(type), "pk": snippet_id},
        )
        return {"deleted": True, "type": type, "snippet_id": snippet_id}

    @wagtail_tool(
        server,
        name="snippets_actions_delete",
        annotations=DESTRUCTIVE,
        description="Delete a snippet via the actions endpoint — the explicit "
        "`/actions/delete/` variant of `snippets_delete`. On the v3 API both "
        "call the same delete action, so prefer `snippets_delete` and keep "
        'this for parity. Returns `{"deleted": true, "type": ..., "snippet_id": ...}`.',
    )
    def snippets_actions_delete(type: str, snippet_id: int) -> dict[str, object]:
        dispatch.call_operation(
            "snippets_actions_delete",
            path_params={**_type_param(type), "pk": snippet_id},
        )
        return {"deleted": True, "type": type, "snippet_id": snippet_id}

    @wagtail_tool(
        server,
        name="snippets_revisions_list",
        annotations=READ_ONLY,
        description="List a draftable snippet's revisions (most recent first), "
        "each with id, created_at and object_str. Use the ids here with "
        "`snippets_revisions_detail` and `snippets_actions_revert`. Requires "
        "the type to be a RevisionMixin model. Paginated via `limit`/`offset`. "
        f"{max_limit_hint()}",
    )
    def snippets_revisions_list(
        type: str, snippet_id: int, limit: int = 20, offset: int = 0
    ) -> dict[str, object]:
        data = dispatch.call_operation(
            "snippets_revisions_list",
            path_params={**_type_param(type), "pk": snippet_id},
            query={"limit": limit, "offset": offset},
        )
        return {
            "count": data.get("count", len(data.get("items", []))),
            "items": [trim_revision(item) for item in data.get("items", [])],
        }

    @wagtail_tool(
        server,
        name="snippets_revisions_detail",
        annotations=READ_ONLY,
        description="Get one revision's detail for a draftable snippet, "
        "including the full content snapshot (`content_object`) at that point "
        "in time. Use with `snippets_actions_revert` to inspect before "
        "reverting. Requires a RevisionMixin model type.",
    )
    def snippets_revisions_detail(
        type: str, snippet_id: int, revision_id: int
    ) -> dict[str, object]:
        data = dispatch.call_operation(
            "snippets_revisions_detail",
            path_params={
                **_type_param(type),
                "pk": snippet_id,
                "revision_id": revision_id,
            },
        )
        trimmed = trim_revision(data)
        content_object = data.get("content_object")
        if isinstance(content_object, dict):
            trimmed["content_object"] = _trim_snippet(content_object)
        return trimmed

    @wagtail_tool(
        server,
        name="snippets_actions_publish",
        annotations=WRITE,
        description="Publish a draftable snippet's latest revision (creating "
        "one from the draft content if none exists). Requires publish "
        "permission and the type to be a DraftStateMixin model. Returns the "
        "published snippet detail.",
    )
    def snippets_actions_publish(type: str, snippet_id: int) -> dict[str, object]:
        return _trim_snippet(
            dispatch.call_operation(
                "snippets_actions_publish",
                path_params={**_type_param(type), "pk": snippet_id},
            )
        )

    @wagtail_tool(
        server,
        name="snippets_actions_unpublish",
        annotations=DESTRUCTIVE,
        description="Unpublish a live snippet, taking it offline. Requires "
        "publish permission and a DraftStateMixin model type. Returns the "
        "snippet detail.",
    )
    def snippets_actions_unpublish(type: str, snippet_id: int) -> dict[str, object]:
        return _trim_snippet(
            dispatch.call_operation(
                "snippets_actions_unpublish",
                path_params={**_type_param(type), "pk": snippet_id},
            )
        )

    @wagtail_tool(
        server,
        name="snippets_actions_revert",
        annotations=WRITE,
        description="Revert a draftable snippet to an earlier revision, "
        "replacing the current draft content with that revision's and creating "
        "a new revision. `revision_id` comes from `snippets_revisions_list`. "
        "Requires a RevisionMixin model type. Returns the reverted (draft) "
        "content — read `snippets_detail(version='draft')` to confirm.",
    )
    def snippets_actions_revert(
        type: str, snippet_id: int, revision_id: int
    ) -> dict[str, object]:
        return _trim_snippet(
            dispatch.call_operation(
                "snippets_actions_revert",
                path_params={**_type_param(type), "pk": snippet_id},
                body={"revision_id": revision_id},
            )
        )

    @wagtail_tool(
        server,
        name="snippets_actions_copy_for_translation",
        annotations=WRITE,
        description="Copy a translatable snippet for translation into another "
        "`locale` (a language code like 'fr'). Requires a TranslatableMixin "
        "model type and internationalization enabled; the target locale must "
        "exist. Returns the new translated snippet detail.",
    )
    def snippets_actions_copy_for_translation(
        type: str, snippet_id: int, locale: str
    ) -> dict[str, object]:
        copied = dispatch.call_operation(
            "snippets_actions_copy_for_translation",
            path_params={**_type_param(type), "pk": snippet_id},
            body={"locale": locale},
        )
        return _trim_snippet(copied)


_REVISION_KEEP = (
    "id",
    "object_id",
    "created_at",
    "user_id",
    "object_str",
    "approved_go_live_at",
)


def trim_revision(item: dict) -> dict:
    """Trim a snippet RevisionSchema item to the fields an agent needs.

    Mirrors the page revisions trimming so both revision surfaces are shaped
    consistently for agents.
    """
    return {k: v for k, v in item.items() if k in _REVISION_KEEP}
