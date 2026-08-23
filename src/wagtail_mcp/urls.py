from django.urls import path

from wagtail_mcp.views import mcp_endpoint


urlpatterns = [
    path("", mcp_endpoint, name="wagtail_mcp"),
]
