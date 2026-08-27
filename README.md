# Wagtail MCP

> 🚧 this is the first vibe-coded draft of an MCP server prototype for Wagtail. Proceed with caution! Until this is ready, you might prefer to use [wagtail-cli](https://github.com/wagtail/wagtail-cli). See [CMS with AI, not AI CMS: Wagtail 8.0’s new API](https://wagtail.org/blog/cms-with-ai-not-ai-cms-wagtail-80s-new-api/) for context.

A Model Context Protocol (MCP) server for Wagtail, exposing the Wagtail v3 API
as model-callable tools. Point a Claude/OpenCode/Hermes-style agent at a
Wagtail site and let it read content, create pages, upload images, publish and
revert — through the same authenticated operations the v3 API provides.

## What it gives you

- **60 curated tools** covering the full shipped v3 operation surface: pages
  (incl. revisions, move/copy/revert, aliases, translations), images,
  documents, snippets, redirects, sites and locales — plus `api_call` /
  `api_schema`, an OpenAPI-backed escape hatch for anything else.
- **In-process dispatch** — tools call the mounted v3 API inside the process
  via Django's test client, so auth, permissions, validation and action logic
  are the real thing. No network hop, no half-reimplemented client.
- **Bearer-token auth** with Wagtail `APIToken`; the v3 API stays the single
  authority for authorization.
- **Stateless Streamable HTTP** — a Django view that works under WSGI and ASGI,
  with no extra processes.

## Quickstart

wagtail-mcp is a Django app: add `wagtail.api.v3` and `wagtail_mcp`, mount
`/api/v3/` and `/mcp/`, create an API token, point a client at `/mcp/`. See the
full [getting started](docs/getting-started.md).

Point a remote MCP client at the endpoint:

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

## Try the demo

The repo ships `demo/`, a Wagtail site that mounts both the API and the MCP
endpoint and seeds a demo token:

```bash
just demo
```

Then use `demo/`'s token (see `demo/README.md`) in your client config. The
[editorial scenario test](tests/test_editorial_scenario.py) is a complete
worked example an agent can follow.

## Documentation

- [Getting started](docs/getting-started.md)
- [Tool reference](docs/tools.md) — all 60 tools, grouped by resource.
- [Configuration](docs/configuration.md) — settings, deployment, token security.
- [Escape hatch](docs/escape-hatch.md) — `api_call` / `api_schema`.
- [Limitations](docs/limitations.md)
- [API feedback](docs/api-feedback.md)

## Supported versions

This package supports Wagtail 8.0 and up (the v3 API preview), Django 5.2/6.0,
and the [compatible Python versions](https://docs.wagtail.org/en/stable/releases/upgrading.html#compatible-django-python-versions).

## Development

Install dependencies, run the tests, lint, and run the demo (`asgiref.sync`
handles the transport, so `just test` and `just lint` are the normal gates):

```bash
just install
just test
just lint
just demo
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution workflow,
including the agent-behavior eval suite.
