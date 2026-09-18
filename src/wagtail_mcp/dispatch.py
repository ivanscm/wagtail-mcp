"""In-process dispatch against the Wagtail v3 API ("client in code").

Tool calls funnel through here: each call maps an ``operation_id`` to an
HTTP method + path, then dispatches it against the project's mounted v3 API
through Django's test ``Client`` — a real ``HttpRequest`` through the full
request pipeline (auth callbacks, permission checks, exception handlers,
action classes, response serialization), without going over the network. The
request is made as the user whose ``Authorization: Bearer`` token is
forwarded, so v3 remains the single authority for authentication and
permissions.

Django's test ``Client`` is used rather than django-ninja's ``TestClient``:
the latter builds a request that Wagtail's page schemas cannot fully
serialize in-process (page ``html_url`` resolution needs a request with a
real host), while Django's client exercises the genuine WSGI-style path and
handles redirects natively.
"""

import functools

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client

from wagtail_mcp import auth
from wagtail_mcp.errors import APIError


# Request bodies may contain non-{primitive} values (e.g. a ``datetime`` from a
# pydantic schema default); Django's JSON encoder serializes those cleanly.
_json_dumps = DjangoJSONEncoder().encode

# URL mount prefix for the v3 API. wagtail-mcp currently requires the v3 API
# to be mounted at "/api/v3/" (no auto-detection). It is used to fetch the
# OpenAPI document; operation paths are then dispatched using the schema's own
# absolute paths, which already carry this prefix and which the test Client
# needs intact.
MOUNT_PREFIX = "/api/v3/"


class DjangoClient:
    """Thin adapter over ``django.test.Client`` exposing a ``request``-style API.

    Delegates to Django's typed verb methods (``get``/``post``/...) so redirects
    are followed natively, and encodes query params into the URL path. The
    ``request(method, path, data, json, query_params, headers, FILES)``
    signature keeps the ``_client()`` seam that tests patch.
    """

    def __init__(self):
        self._client = Client()

    def request(
        self,
        method,
        path,
        data=None,
        json=None,
        query_params=None,
        headers=None,
        FILES=None,
        host=None,
        port=None,
    ):
        from urllib.parse import urlencode

        verb = method.upper()
        if verb not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError(f"Unsupported HTTP method {method!r}")
        call = getattr(self._client, verb.lower())

        if query_params:
            qs = {k: v for k, v in query_params.items() if v is not None}
            if qs:
                sep = "&" if "?" in path else "?"
                path = f"{path}{sep}{urlencode(qs)}"

        client_kwargs = {}
        if headers:
            client_kwargs.update(
                {
                    f"HTTP_{name.upper().replace('-', '_')}": value
                    for name, value in headers.items()
                }
            )
        # The real caller host, forwarded so absolute API URLs (``detail_url`` /
        # ``html_url``) resolve to the caller rather than ``testserver``.
        # Django's test client reads these from ``META``/environ directly.
        if host:
            client_kwargs["HTTP_HOST"] = host
        if port:
            client_kwargs["SERVER_PORT"] = port
        if json is not None:
            client_kwargs["data"] = _json_dumps(json)
            client_kwargs["content_type"] = "application/json"
        elif data is not None or FILES:
            # Django's test client has no ``files=`` kwarg: file uploads are
            # passed inline in the ``data`` mapping as ``SimpleUploadedFile``
            # values. Merge form fields and files into a single mapping.
            merged = dict(data or {})
            if FILES:
                merged.update(FILES)
            client_kwargs["data"] = merged

        # Follow HTTP redirects transparently so ``pages_find`` (which the v3
        # API answers with a 302 to the page-detail URL) works like a real
        # HTTP client instead of surfacing a raw 302.
        return call(path, follow=True, **client_kwargs)


def _client() -> DjangoClient:
    """Return a fresh Django test client per call.

    Tool handlers run in concurrent worker threads; ``django.test.Client`` is
    stateful, so a process-wide cached instance would not be thread-safe. A
    fresh ``Client()`` per dispatch is cheap.
    """
    return DjangoClient()


def _host_parts() -> tuple[str | None, str | None]:
    """Resolve ``auth.current_host`` into ``(Host header, SERVER_PORT)`` parts.

    Both ``openapi()`` and ``call_operation()`` forward the caller's real Host
    into the in-process client: under a strict ``ALLOWED_HOSTS`` (production,
    ``DEBUG=False``) Django's client default of ``testserver`` would fail host
    validation, and absolute API URLs would resolve to the wrong host. Any
    ``:port`` suffix is split off the value; the port is passed separately as
    ``SERVER_PORT``.
    """
    host = auth.current_host.get()
    if not host:
        return None, None
    if ":" in host:
        hostname, _, candidate = host.rpartition(":")
        if candidate.isdigit():
            return hostname, candidate
    return host, None


@functools.cache
def openapi() -> dict:
    """The live OpenAPI 3.1 document for the mounted v3 API (cached).

    Cache is cleared with ``openapi.cache_clear()``; use ``clear_caches()`` to
    clear all dispatch caches at once.
    """
    host_header, port = _host_parts()
    response = _client().request(
        "GET",
        f"{MOUNT_PREFIX.rstrip('/')}/openapi.json",
        host=host_header,
        port=port,
    )
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


@functools.cache
def operation_map() -> dict:
    """Map ``operation_id`` → ``(http_method, url_path)``.

    Paths match the OpenAPI absolute paths (including the mount prefix), as
    the Django test Client requires the full mounted URL.
    """
    schema = openapi()
    result = {}
    for path, methods in schema["paths"].items():
        for method, spec in methods.items():
            if "operationId" in spec:
                result[spec["operationId"]] = (method, path)
    return result


def clear_caches() -> None:
    """Invalidate every cached dispatch datum (OpenAPI schema + operation map)."""
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
        method, path = operation_map()[operation_id]
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
        path = path.format(**(path_params or {}))
    except KeyError as exc:
        raise APIError(
            400,
            {
                "title": "Missing path parameter",
                "status": 400,
                "detail": f"Operation {operation_id!r} requires path parameter {exc.args[0]!r}.",
            },
        ) from None
    except (IndexError, ValueError) as exc:
        # A malformed template (e.g. "{}" without a field, or an unmatched
        # brace) raises IndexError/ValueError rather than KeyError. Surface
        # these as clean APIErrors instead of leaking raw exceptions out of
        # the tool.
        raise APIError(
            500,
            {
                "title": "Invalid path template",
                "status": 500,
                "detail": f"Path template for operation {operation_id!r} is malformed: {exc}.",
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

    # Forward the request's real Host into the in-process client (see
    # ``_host_parts``) so absolute API URLs (e.g. ``meta.detail_url``/
    # ``meta.html_url``) resolve to the caller's host rather than Django's
    # hardcoded ``testserver``, and host validation passes under strict
    # ``ALLOWED_HOSTS``.
    host_header, port = _host_parts()

    response = _client().request(
        method.upper(),
        path,
        data=form,
        json=body,
        query_params={k: v for k, v in (query or {}).items() if v is not None},
        headers=headers,
        FILES=upload_files,
        host=host_header,
        port=port,
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
