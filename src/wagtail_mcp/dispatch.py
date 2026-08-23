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

    Cache is cleared with ``openapi.cache_clear()``; use ``clear_caches()`` to
    clear all dispatch caches at once.
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
    """Return the URL mount prefix shared by most OpenAPI paths (e.g. ``/api/v3/``),
    or ``""`` if none can be established.

    OpenAPI paths are absolute (with the mount prefix, since that is how the
    v3 API is served), but ``TestClient`` resolves against the *unmounted*
    ``api.urls`` patterns, so the prefix must be stripped back before dispatch.

    Robust scheme (chosen): compute the longest common leading path prefix
    among the paths that share the **most common first segment**, ignoring any
    path that does not share it. A single odd or absolute path therefore cannot
    collapse the whole detection to ``""`` and silently break every dispatch —
    the previous "common to ALL paths" approach had exactly that failure mode.
    """
    if not paths:
        return ""
    firsts = {}
    for p in paths:
        first = p.strip("/").split("/")[0]
        firsts[first] = firsts.get(first, 0) + 1
    if not firsts:
        return ""
    top = max(firsts, key=firsts.get)
    segments = [p.strip("/").split("/") for p in paths if p.startswith("/" + top)]
    if not segments:
        return ""
    prefix = []
    for i, seg in enumerate(segments[0]):
        if all(len(other) > i and other[i] == seg for other in segments[1:]):
            prefix.append(seg)
        else:
            break
    return "/" + "/".join(prefix) if prefix else ""


@functools.cache
def operation_map() -> dict:
    """Map ``operation_id`` → ``(http_method, url_path)``.

    Paths are stripped of the mount prefix so they resolve against Ninja's
    in-process ``TestClient``. Derives the prefix lazily from the schema it is
    already holding, so there is no stale import-time value.
    """
    schema = openapi()
    prefix = _mount_prefix(list(schema["paths"]))
    result = {}
    for path, methods in schema["paths"].items():
        resolver_path = path
        if prefix and resolver_path.startswith(prefix):
            resolver_path = resolver_path[len(prefix) :].lstrip("/")
        for method, spec in methods.items():
            if "operationId" in spec:
                result[spec["operationId"]] = (method, resolver_path)
    return result


def clear_caches() -> None:
    """Invalidate every cached dispatch datum (OpenAPI schema + operation map).

    Keeps ``openapi.cache_clear()`` working as the brief-pinned single-cache
    clear, while allowing callers to purge the whole dispatch cache coherently.
    """
    openapi.cache_clear()
    operation_map.cache_clear()


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
        is ``{field: (filename, bytes, content_type)}``. Mutually exclusive with
        ``body``.
      - ``token``: plaintext ``wagtail_...`` token; omitted falls back to
        ``auth.current_token``.

    Returns ``None`` for empty responses (e.g. 204). Raises
    ``wagtail_mcp.errors.APIError(status, problem)`` on non-2xx responses.
    """
    if body is not None and (form is not None or files is not None):
        raise APIError(
            400,
            {
                "title": "Invalid operation call",
                "status": 400,
                "detail": "Pass either a JSON `body` or form data (`form`/`files`), not both.",
            },
        )

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

    try:
        path = path_template.format(**(path_params or {}))
    except KeyError as exc:
        raise APIError(
            400,
            {
                "title": "Missing path parameter",
                "status": 400,
                "detail": f"Operation {operation_id!r} requires path parameter {exc.args[0]!r}.",
            },
        ) from None

    upload_files = None
    if files:
        upload_files = {
            field: SimpleUploadedFile(filename, content, content_type=content_type)
            for field, (filename, content, content_type) in files.items()
        }

    resolved_token = token or auth.current_token.get()
    headers = {}
    if resolved_token:
        headers = {"Authorization": f"Bearer {resolved_token}"}

    response = _client().request(
        method.upper(),
        path,
        data=form,
        json=body,
        query_params={k: v for k, v in (query or {}).items() if v is not None},
        headers=headers,
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
