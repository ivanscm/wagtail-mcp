from mcp.server.mcpserver import MCPServer


def register_all(server: MCPServer) -> None:
    """Register every tool module's tools onto the MCP server.

    Task 6+ appends modules to the ``_MODULES`` tuple and each module
    implements ``register(server)``. For now there are no tool modules, so the
    server exposes an empty tool list. ``register_all`` must only ever *append*,
    preserving entries added by earlier tasks.
    """
    _MODULES: tuple = ()
    for module in _MODULES:
        module.register(server)
