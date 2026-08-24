# Getting started

Add wagtail-mcp to a Wagtail project.

## Requirements

- Wagtail **8.0 or newer** (the v3 API is a preview feature of Wagtail 8.0,
  and wagtail-mcp is built on it).
- Django 5.2 / 6.0 and a compatible Python (see the version classifiers in
  `pyproject.toml`).
- `django-ninja` arrives transitively via Wagtail (the v3 API is built on it);
  wagtail-mcp dispatches through its in-process test client, so the effective
  ninja floor is pinned by Wagtail's requirement.

The `mcp` dependency is pinned to the exact version the transport was built
against; bumps are deliberate, documented changelog entries.

## Install

Once published:

```bash
uv add wagtail-mcp
# or
pip install wagtail-mcp
```

While developing against a checkout, point uv at the local package instead:

```toml
[tool.uv.sources]
wagtail-mcp = { path = "..", editable = true }
```

> Note for running the v3 API during development: Wagtail 8.0 only ships a
> release candidate on PyPI at the time of writing (`8.0rc2`); `>=8.0`
> resolves to the release candidate or a pre-release. In this repo's
> `pyproject.toml` the dev lock uses a `[tool.uv.sources]` path override to
> the sibling `wagtail` checkout. Your project only needs this if you must
> pin to a pre-release for early v3 evaluation.

## Settings

Add the v3 API to `INSTALLED_APPS` (wagtail-mcp refuses to start without it):

```python
INSTALLED_APPS = [
    # ...your apps...
    "wagtail.api.v3",
    "wagtail_mcp",
]
```

Two notes on app coverage:

- The v3 API's route groups are registered by the apps that own them, so the
  tools you get depend on which Wagtail apps are installed. **`wagtail.locales`
  is easy to forget** — without it in `INSTALLED_APPS`, the whole `locales_*`
  tool group silently disappears from the schema (no error or hint). Install
  `wagtail.images`, `wagtail.documents`, `wagtail.snippets`,
  `wagtail.contrib.redirects`, `wagtail.sites` and `wagtail.locales` for the
  corresponding tool groups. Pages, `schema_*` and `whoami` are always present.
- Set `WAGTAILAPI_BASE_URL` so absolute URLs in responses (e.g.
  `meta.detail_url`, `meta.html_url`) resolve to your real public origin rather
  than the request's host. See [configuration](configuration.md).

## Mount the URLs

```python
# yourproject/urls.py
from django.urls import include, path
from wagtail.api.v3.urls import api as api_v3

urlpatterns = [
    path("api/v3/", api_v3.urls),
    path("mcp/", include("wagtail_mcp.urls")),
]
```

**Mount the v3 API at `/api/v3/`.** wagtail-mcp currently assumes this exact
path (see [limitations](limitations.md): it does not yet detect the mount
prefix). A different prefix such as `/api/v3-preview/` is not supported today.

## Create an API token

wagtail-mcp authenticates with a Wagtail `APIToken` (the same model the v3 API
uses). Two ways to create one:

**Wagtail admin.** In the admin's Settings menu, open **API tokens** and create
a token for a user with the permissions needed for the operations you'll
serve. Wagtail shows the plaintext only once, at creation.

**Python / shell** (e.g. via `manage.py shell`):

```python
from django.contrib.auth import get_user_model
from wagtail.models import APIToken

user = get_user_model().objects.get(username="admin")
_, token = APIToken.create_token(user=user, name="mcp-agent")
print(token)  # e.g. wagtail_xxxxxxxxxxxxxxxx...
```

Keep the plaintext somewhere your client can read (the demo writes it to
`demo/.demo_token`, mode `0600`).

## Point an MCP client at the server

The endpoint is a stateless Streamable HTTP server. Point any MCP client that
speaks that transport (OpenCode, Hermes, Claude) at your `/mcp/` URL with a
bearer header. It must send `Content-Type: application/json` and an `Accept`
that includes both `application/json` and `text/event-stream`; well-behaved
MCP clients send these by default.

**OpenCode** (`.opencode.json` or your global opencode config):

```json
{
  "mcp": {
    "wagtail": {
      "type": "remote",
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer <your-token>",
        "Content-Type": "application/json"
      }
    }
  }
}
```

**Hermes / any remote MCP client:** point it at the same URL with an
`Authorization: Bearer <token>` header and the Accept header above.

## Smoke test

With your server running, obtain a token for your client (instead of typing a
new one each test, reuse a stored token from your client config):

```bash
# The demo writes a token to demo/.demo_token after `just demo`.
TOKEN=$(cat demo/.demo_token)
```

Or create a fresh one via Wagtail's shell. Using the demo's settings (run this
from the `demo/` directory, after `just demo` has created the `admin` user):

```bash
TOKEN=$(cd demo && uv run python manage.py shell -c "
from django.contrib.auth import get_user_model
from wagtail.models import APIToken
user = get_user_model().objects.get(username='admin')
_, token = APIToken.create_token(user=user, name='mcp-smoke')
print(token)
")
```

Then initialize the MCP handshake:

```bash
curl -s http://localhost:8000/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

List the available tools the same way with `{"method":"tools/list"}` — you
should see the 60 tools documented in the [tool reference](tools.md). If you
get a 406, check your `Accept` header; if 401, check your token (see
[configuration](configuration.md) for `require_auth`).

## Try the demo

The repo ships a `demo/` Wagtail site that mounts both the v3 API and the MCP
endpoint and seeds a demo token:

```bash
just demo
```

See `demo/README.md` for the quickstart, the demo token location, and a full
manual smoke test. Use the [editorial scenario](../tests/test_editorial_scenario.py)
as a model of a complete agent-driven task: schema lookup → find parent →
upload image → create page with markdown → publish → verify the live URL.
