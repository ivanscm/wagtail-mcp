# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-24

### Added

- **Initial release: an MCP server for the Wagtail v3 API.**
- In-process dispatch: tool calls hit the mounted v3 API inside the process via
  Django's test client, reusing real auth, permissions, validation and action
  logic — no network hop.
- Stateless Streamable HTTP transport mounted as a Django view (`/mcp/`),
  working under WSGI and ASGI with no extra processes.
- Bearer-token authentication with Wagtail `APIToken`, forwarded into the v3
  API (the single authority for authorization); gated by `WAGTAIL_MCP
  require_auth` (default `True`).
- **60 curated tools** across pages (list/find/detail + create/update/delete +
  publish/unpublish/copy/move/revert/aliases/translations + revisions), images,
  documents, snippets (generic, keyed by type), redirects, sites and locales —
  each with MCP annotations (read-only/destructive/idempotent hints) and
  agent-oriented descriptions.
- `api_call` and `api_schema`: an OpenAPI-backed escape hatch for any v3
  operation, including revision revert and `db_html` image-embed writes.
- Flattened, agent-ergonomic inputs (markdown bodies, base64 uploads) and
  shaped responses (pagination `next_offset`, trimmed meta, RFC 7807 errors
  flattened with recovery hints).
- Demo site (`demo/`) with v3 API + MCP mounts and a seeded demo API
  token (`just demo`).
- Documentation: getting started, full tool reference, configuration,
  escape-hatch guide, limitations, and API feedback.
- Promptfoo eval suite (promptfoo + OpenCode SDK) verifying a real model uses
  the tools against the demo site, with state-graded assertions.

### Changed

- None (initial release).

### Removed

- None (initial release).

<!-- TEMPLATE - keep below to copy for new releases -->
<!--


## [x.y.z] - YYYY-MM-DD

### Added

- ...

### Changed

- ...

### Removed

- ...

-->
