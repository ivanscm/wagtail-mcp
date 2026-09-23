# Wagtail MCP

> 🚧🤖 this is an early vibe-coded prototype of an MCP server for Wagtail. Proceed with caution! Until this is ready, you might prefer to use the [wagtail-cli](https://github.com/wagtail/wagtail-cli). See [CMS with AI, not AI CMS: Wagtail 8.0’s new API](https://wagtail.org/blog/cms-with-ai-not-ai-cms-wagtail-80s-new-api/) for context.

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro) server for Wagtail, exposing the Wagtail v3 API operations as model-callable tools.

## Capabilities

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

Using the package: [docs](docs/README.md).

- [Getting started](docs/getting-started.md)
- [Tool reference](docs/tools.md)
- [Configuration](docs/configuration.md)
- [Admin agent](docs/admin-agent.md)
- [Escape hatch](docs/escape-hatch.md)
- [Limitations](docs/limitations.md)

Changing the package: [contributing](docs/contributing/README.md).

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and releases.
