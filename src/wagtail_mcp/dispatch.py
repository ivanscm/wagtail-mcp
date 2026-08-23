"""In-process dispatch against the Wagtail v3 API ("client in code").

Tool calls funnel through here: each call maps an ``operation_id`` to an
HTTP method + path from the project's OpenAPI schema, then dispatches it
against the mounted v3 ``NinjaAPI`` *without* going over the network. Ninja's
in-process ``TestClient`` builds a real ``HttpRequest`` and runs the actual
view — auth callbacks, permission checks, validation, action classes and the
RFC 7807 error path all execute unchanged. The request is made as the user
whose ``Authorization: Bearer`` token is forwarded, so v3 remains the single
authority for authentication and permissions.
"""

import functools

from django.core.files.uploadedfile import SimpleUploadedFile
from ninja.testing import TestClient
from wagtail.api.v3.api import api

from wagtail_mcp import auth
from wagtail_mcp.errors import APIError


def _client() -> TestClient:
    """A fresh Ninja test client bound to the project's v3 API instance."""
    return TestClient(api)


@functools.cache
def openapi() -> dict:
    """The live OpenAPI 3.1 document for the mounted v3 API (cached).

    Cache is cleared with ``openapi.cache_clear()``.
    """
    response = _client().get("/openapi.json")
    if response.status_code != 200:
        raise APIError(
            response.status_code,
            {
                "title": "Cannot load OpenAPI schema",
                "status": response.status_code,
                "detail": "The v3 API's /openapi.json endpoint did not respond with 200.",
            },
        )
    return response.json()


def _mount_prefix(paths):
    """Return the URL mount prefix shared by every OpenAPI path (e.g. ``/api/v3/``).

    OpenAPI paths are absolute (with the mount prefix, since that is how the
    v3 API is served), but ``TestClient`` resolves against the *unmounted*
    ``api.urls`` patterns. We strip the prefix back off before dispatching.
    Fall back to ``""`` if no common leading path segment exists.
    """
    if not paths:
        return ""
    segments = [p.strip("/").split("/") for p in paths]
    prefix = []
    for i, seg in enumerate(segments[0]):
        if all(len(other) > i and other[i] == seg for other in segments[1:]):
            prefix.append(seg)
        else:
            break
    return "/" + "/".join(prefix) if prefix else ""


MOUNT_PREFIX = _mount_prefix(list(openapi()["paths"]))


@functools.cache
def operation_map() -> dict:
    """Map ``operation_id`` → ``(http_method, url_path)``.

    Paths are stripped of the mount prefix so they resolve against Ninja's
    in-process ``TestClient``. Cached alongside ``openapi()``.
    """
    schema = openapi()
    result = {}
    for path, methods in schema["paths"].items():
        resolver_path = path
        if MOUNT_PREFIX and resolver_path.startswith(MOUNT_PREFIX):
            resolver_path = resolver_path[len(MOUNT_PREFIX) :].lstrip("/")
        for method, spec in methods.items():
            if "operationId" in spec:
                result[spec["operationId"]] = (method, resolver_path)
    return result


def call_operation(
    operation_id,
    *,
    path_params=None,
    query=None,
    body=None,
    form=None,
    files=None,
    token=None,
):
    """Execute a v3 operation in-process and return its parsed JSON response.

    Args passed through to the v3 API:
      - ``path_params``: substituted into URL path templates (e.g. ``page_id``).
      - ``query``: query-string parameters, e.g. ``{"limit": 20, "offset": 0}``
        (``None`` values are dropped).
      - ``body``: JSON request body for ``post``/``patch``/``put`` operations.
      - ``form`` + ``files``: form-encoded fields for upload operations — ``files``
        is ``{field: (filename, bytes, content_type)}``.
      - ``token``: plaintext ``wagtail_...`` token; omitted falls back to
        ``auth.current_token``.

    Returns ``None`` for empty responses (e.g. 204). Raises
    ``wagtail_mcp.errors.APIError(status, problem)`` on non-2xx responses.
    """
    try:
        method, path_template = operation_map()[operation_id]
    except KeyError:
        raise APIError(
            400,
            {
                "title": "Unknown operation",
                "status": 400,
                "detail": (
                    f"Unknown operation_id {operation_id!r}. Known prefixes: "
                    + ", ".join(sorted({k.split("_")[0] for k in operation_map()}))
                ),
            },
        ) from None

    path = path_template.format(**(path_params or {}))

    upload_files = None
    if files:
        upload_files = {
            field: SimpleUploadedFile(filename, content, content_type=content_type)
            for field, (filename, content, content_type) in files.items()
        }

    response = _client().request(
        method.upper(),
        path,
        data=form,
        json=body,
        query_params={k: v for k, v in (query or {}).items() if v is not None},
        headers={"Authorization": f"Bearer {token or auth.current_token.get()}"},
        FILES=upload_files,
    )

    if response.status_code >= 400:
        try:
            problem = response.json()
        except Exception:
            problem = {"title": "Unexpected response", "status": response.status_code}
        problem.setdefault("status", response.status_code)
        raise APIError(response.status_code, problem)

    if response.status_code == 204 or not response.content:
        return None
    return response.json()
