# Wagtail MCP

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for
Wagtail. It exposes the [Wagtail v3 API](https://docs.wagtail.org/en/stable/advanced_topics/api/v3/index.html)
as tools an agent can call: read content, create pages, upload images, publish
and revert, using the same `APIToken` bearer auth as the v3 API.

These pages are for people installing and calling the package. Changing the
package is covered under [Contributing](contributing/README.md).

## Guides

- [Getting started](getting-started.md) — install, settings, URL mounts, tokens, a smoke test.

## How-to

- [Admin agent](admin-agent.md) — the same tools as a chat in the Wagtail admin.
- [Escape hatch](escape-hatch.md) — call any v3 operation with `api_call` / `api_schema`.

## Reference

- [Tools](tools.md) — all 60 tools, grouped by resource.
- [Configuration](configuration.md) — `WAGTAIL_MCP`, deployment, token security.
- [Limitations](limitations.md) — what the package does not do yet.
