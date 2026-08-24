# Limitations

This page documents current wagtail-mcp limitations. It is intentionally short
for now and will be expanded as the package matures (the design spec tracks the
intended scope in `local/superpowers/specs/2026-08-23-mcp-server-design.md`).

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

## No SSE streaming transport

The MCP endpoint serves **stateless Streamable HTTP with JSON responses only**
(one POST = one JSON-RPC response). It does not serve the HTTP GET/SSE stream,
so long-lived server-push sessions are unsupported. This is fine for
OpenCode, Hermes, and Claude-style clients that POST JSON-RPC.

## Other known gaps

- **No OAuth yet** — authentication uses Wagtail `APIToken` bearer tokens
  (see the roadmap).
- **No workflow/moderation endpoints** — the v3 API does not expose them yet.
- Redirects returned by the API are followed transparently (e.g. `pages_find`
  responds with a 302 to the page detail; the tool follows it).