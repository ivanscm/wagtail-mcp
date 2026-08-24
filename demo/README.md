# Demo site

A Wagtail project for exercising `wagtail-mcp` locally. It mounts the v3 API at
`/api/v3/` and the MCP server at `/mcp/`.

## Run

```bash
just demo
```

`just demo` runs, in order:

1. `migrate` — bring the demo database up to date.
2. `load_initial_data` — create the `admin` user (`admin` / `changeme`) and a
   set of bakerydemo-style blog content.
3. `create_demo_api_token` — create (or refresh) an `mcp-demo` Wagtail API token
   for `admin` and record its plaintext in **`demo/.demo_token`** (gitignored).
4. `runserver` — serve the site at <http://localhost:8000/>.

When the server is up:

- The v3 API is at <http://localhost:8000/api/v3/> (schema at
  <http://localhost:8000/api/v3/openapi.json>).
- The MCP endpoint is at <http://localhost:8000/mcp/>.

## Your MCP token

The API token for the MCP server is written to `demo/.demo_token`. It is created
on the first `just demo` run and left untouched on later runs as long as the
file is present (Wagtail only shows an API token's plaintext once, at creation).
Delete `demo/.demo_token` (and the `mcp-demo` token in the admin's Settings →
API tokens) to force a fresh one.

### Manual smoke test

```bash
TOKEN=$(cat demo/.demo_token)

# Initialize the MCP handshake.
curl -s -X POST http://localhost:8000/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'

# List the available tools (60 expected).
curl -s -X POST http://localhost:8000/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)['result']['tools']), 'tools')"
```

## Pointing a client at the MCP server

### OpenCode

```json
{
  "mcp": {
    "wagtail": {
      "type": "remote",
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer <your token from demo/.demo_token>",
        "Content-Type": "application/json"
      }
    }
  }
}
```

### Hermes / other remote MCP clients

Point the client at the same remote URL:
<http://localhost:8000/mcp/> with an `Authorization: Bearer <token>` header and
`Accept: application/json, text/event-stream`. Any MCP client that speaks
Streamable HTTP can connect.