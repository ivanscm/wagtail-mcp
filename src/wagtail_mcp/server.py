import functools

from mcp.server.mcpserver import MCPServer


@functools.cache
def get_server() -> MCPServer:
    """Return the process-wide MCP server singleton (tools registered once)."""
    server = MCPServer(name="wagtail-mcp")
    from wagtail_mcp.tools import register_all

    register_all(server)
    return server
