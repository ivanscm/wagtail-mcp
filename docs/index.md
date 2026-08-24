# wagtail-mcp

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for
Wagtail, exposing the [Wagtail v3 API](https://docs.wagtail.org/en/stable/advanced_topics/api/v3/index.html)
as model-callable tools. It lets a Claude/OpenCode/Hermes-style agent do real
CMS work — read content, create pages, upload images, publish and revert —
through the same authenticated operations the v3 API provides, without a
custom integration per client.

## What it is

- **A Django app**, installed into a Wagtail project, exposing one mountable
  MCP endpoint (`/mcp/`) over stateless [Streamable
  HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#streamable-http).
- **60 curated tools** covering the whole shipped v3 operation surface —
  pages (incl. revisions, move/copy/revert, aliases, translations), images,
  documents, snippets, redirects, sites and locales — plus `api_call` and
  `api_schema`, an OpenAPI-backed escape hatch for anything not hand-curated.
- **In-process dispatch**: tool calls hit the mounted v3 API *inside* the
  process via Django's test client, so auth, permissions, validation and
  action logic are the real thing — no network hop, no half-reimplemented
  client.

It authenticates with Wagtail API tokens (`APIToken`); the bearer token is
resolved at the MCP boundary and forwarded into the v3 API, which remains the
single point of truth for authorization.

## Documentation map

- [**Getting started**](getting-started.md) — install, settings, mounts, tokens, client setup, smoke test.
- [**Tool reference**](tools.md) — all 60 tools, grouped by resource.
- [**Configuration**](configuration.md) — `WAGTAIL_MCP` settings, deployment, token security.
- [**Escape hatch**](escape-hatch.md) — driving any v3 operation with `api_call` / `api_schema`.
- [**Limitations**](limitations.md) — what it does and doesn't do yet.
- [**API feedback**](api-feedback.md) — findings we'd like to feed back to the Wagtail v3 API.

## A quick example

```json
{
  "mcp": {
    "wagtail": {
      "type": "remote",
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer <your-api-token>",
        "Content-Type": "application/json"
      }
    }
  }
}
```

With that config, an agent can call e.g. `pages_list`, `images_create`,
`pages_create`, and `pages_actions_publish` to build and ship a page end to
end. Head to [getting-started](getting-started.md) for the full walkthrough.