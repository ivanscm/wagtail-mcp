# Limitations

This page documents current wagtail-mcp limitations — the scope it deliberately
does not cover and the coupling that comes with reusing the Wagtail v3 API.

## In-process dispatch via Django's test Client

wagtail-mcp calls the Wagtail v3 API **in-process**, without going over the
network: each tool invocation dispatches its operation through
[Django's in-process test `Client`](https://docs.djangoproject.com/en/stable/topics/testing/tools/#the-test-client)
`django.test.Client`. This reuses the full request pipeline (auth callbacks,
permission checks, exception handlers, action classes, response
serialization) while avoiding an HTTP round-trip and a self-call back into the
site.

What this means:

- **Absolute API URLs require a base URL.** The v3 API builds self-referential
  links such as `meta.detail_url` and `meta.html_url` from the request's host
  (via `Site.find_for_request`) or from `WAGTAILAPI_BASE_URL` when set. In
  production, set `WAGTAILAPI_BASE_URL` on your site so these links are
  stable and correct regardless of the request host. The package cannot safely
  guess your public host.
- **Host forwarding.** When `WAGTAILAPI_BASE_URL` is *not* set, wagtail-mcp
  forwards the incoming MCP request's `Host` header into the in-process client
  (`auth.current_host`), so `detail_url`/`html_url` resolve to the caller's
  host rather than Django's hardcoded `testserver`. This is a fallback, not a
  substitute for setting `WAGTAILAPI_BASE_URL`.
- **Non-POST → 405.** The endpoint serves `POST` only; GET (the SSE stream) is
  not mounted, so non-POST methods return 405 before any auth check.

## Transport and SDK coupling

- **Stateless Streamable HTTP, JSON responses only.** One POST = one JSON-RPC
  response; no SSE/GET streaming, no server-side sessions, no long-lived push.
  Fine for the current clients (which POST JSON-RPC), but remote clients that
  rely on SSE fallback or server-push notifications are unsupported.
- **MCP SDK pinned exactly.** `mcp` is pinned to the exact version the
  transport was built against (currently `2.0.0`). Bumps must be deliberate:
  verify the ASGI-session-manager lifecycle (which we construct per request)
  and the `MCPServer._lowlevel_server` accessor we use to embed the transport
  in a Django view. That `_lowlevel_server` is the SDK's **private** attribute
  — there is no portable public accessor on `MCPServer`, so this is coupling
  worth re-checking on SDK upgrades.

## Authentication

- **No OAuth (yet).** Authentication uses Wagtail `APIToken` bearer tokens.
  Planned roadmap: OAuth 2.1 for the MCP HTTP transport (e.g. via
  `django-oauth-toolkit` or the MCP SDK's auth-provider hooks). Because both
  the token path and an OAuth path resolve to the same Wagtail user model and
  only change the identity resolution at the MCP boundary, the 60 tools are
  agnostic to the choice — the migration should be transparent to tool callers.
- **Plaintext token in client configs.** MCP client configs typically store the
  bearer token in plaintext; keep them permission-restricted and out of version
  control, and rotate tokens (revocation applies immediately). See
  [configuration](configuration.md).

## Coverage gaps

- **No workflow/moderation endpoints.** The v3 API does not expose submitting,
  approving or rejecting workflow tasks yet, so there are no corresponding
  tools.
- **No tags write on images/documents.** The v3 image/document write schemas
  expose no tags input (tags are read-only under `meta`) — a gap we'd like to
  feed back upstream (see [api-feedback](api-feedback.md)).
- **Markdown image embeds are dropped.** Rich-text writes as Markdown do not
  preserve image embeds (the v3 sanitizer drops them silently); the workaround
  is a `db_html` body via `api_call` (see [escape-hatch](escape-hatch.md)).
- **v3 API must be mounted at `/api/v3/`.** wagtail-mcp dispatches against the
  v3 API mounted at exactly `/api/v3/` — it does not (yet) detect a different
  mount prefix from the OpenAPI schema. A site that mounts the API at another
  prefix (e.g. `/api/v3-preview/`) is unsupported today; automatic prefix
  discovery is a possible future enhancement.
- **Writable fields require `writable=True`.** Only `api_fields` marked
  `writable=True` appear in the v3 create/update schemas. A project whose
  content model exposes a field read-only on the API cannot write it through
  wagtail-mcp until the model marks it writable — the field is silently omitted
  from the write schema rather than erroring.
- **Snippet drafts/live state.** The snippet read schema's `meta` does not
  surface a `live` flag, so agents can't glean publish state from a snippet
  detail read alone (they must know whether the type is draftable).
- Redirects returned by the API are followed transparently (e.g. `pages_find`
  responds with a 302 to the page detail; the tool follows it).
