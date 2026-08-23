"""Meta tools: whoami, schema discovery, and the OpenAPI escape hatch.

These are the smallest, most discoverable tools an agent reaches for first,
and the only place the escape hatch (``api_call``/``api_schema``) lives. All
read-only except ``api_call``, which can drive any v3 mutation.
"""

from wagtail_mcp import dispatch
from wagtail_mcp.errors import APIError
from wagtail_mcp.tools.common import READ_ONLY, WRITE, wagtail_tool


def register(server):
    @wagtail_tool(
        server,
        name="whoami",
        annotations=READ_ONLY,
        description="Return the Wagtail user the API token belongs to (username, "
        "email, permissions flags). Call this first to confirm that "
        "authentication against the project's v3 API works.",
    )
    def whoami() -> dict:
        return dispatch.call_operation("whoami")

    @wagtail_tool(
        server,
        name="schema_list",
        annotations=READ_ONLY,
        description="List all content types the v3 API exposes on this project "
        "(page types and API-enabled snippet types), as "
        "'app_label.ModelName' strings.",
    )
    def schema_list() -> dict:
        return dispatch.call_operation("schema_list")

    @wagtail_tool(
        server,
        name="schema_detail",
        annotations=READ_ONLY,
        description="Get the full field schema for one content type (e.g. "
        "'wagtail_mcp_test.ContentPage') including required fields. Call "
        "before creating or updating instances of that type.",
    )
    def schema_detail(type_name: str) -> dict:
        return dispatch.call_operation(
            "schema_detail", path_params={"type_name": type_name}
        )

    @wagtail_tool(
        server,
        name="api_schema",
        annotations=READ_ONLY,
        description="Read the project's full OpenAPI 3.1 schema, or one named "
        "component when `component` is given. Use to discover exact operation "
        "paths and payload shapes for api_call.",
    )
    def api_schema(component: str | None = None) -> dict:
        doc = dispatch.openapi()
        if component is None:
            return {
                "paths": sorted(doc["paths"]),
                "components": sorted(doc.get("components", {}).get("schemas", {})),
            }
        schemas = doc.get("components", {}).get("schemas", {})
        try:
            return schemas[component]
        except KeyError:
            available = ", ".join(sorted(schemas)) or "none"
            raise APIError(
                404,
                {
                    "title": "Unknown schema component",
                    "status": 404,
                    "detail": f"No schema component named {component!r}. "
                    f"Available: {available}",
                },
            ) from None

    @wagtail_tool(
        server,
        name="api_call",
        annotations=WRITE,
        description="Escape hatch: call ANY v3 API operation by operation_id "
        "(see api_schema for the full list). Prefer the dedicated tools; use "
        "this for operations without one (e.g. revisions). Specify JSON bodies "
        "via `body` and URL/path variables via `path_params`.",
    )
    def api_call(
        operation_id: str,
        path_params: dict | None = None,
        query: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        result = dispatch.call_operation(
            operation_id,
            path_params=path_params,
            query=query,
            body=body,
        )
        # ``call_operation`` returns None for 204/empty responses; normalise to a
        # JSON object so the tool result stays a dict.
        return result or {}
