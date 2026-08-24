from mcp.server.mcpserver import MCPServer


def _tool_modules():
    """Import tool modules lazily to avoid import cycles with dispatch/common.

    Return the modules whose ``register(server)`` contributes tools. Modules
    are appended by later tasks; ``register_all`` always appends, preserving
    entries added by earlier tasks.
    """
    from wagtail_mcp.tools import documents, images, meta, pages, snippets

    return [meta, pages, images, documents, snippets]


def register_all(server: MCPServer) -> None:
    """Register every tool module's tools onto the MCP server."""
    for module in _tool_modules():
        module.register(server)
