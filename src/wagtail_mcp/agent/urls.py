"""AG-UI endpoint URLconf. Mount from the project root, before the admin include.

See docs/admin-agent.md.
"""

from django.urls import path

from wagtail_mcp.agent.server import WagtailMCPAgentServer


agent_server = WagtailMCPAgentServer()

urlpatterns = [
    path("", agent_server.urls),
]
