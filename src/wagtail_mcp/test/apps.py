from django.apps import AppConfig


class WagtailMCPTestAppConfig(AppConfig):
    label = "wagtail_mcp_test"
    name = "wagtail_mcp.test"
    verbose_name = "Wagtail MCP tests"
    default_auto_field = "django.db.models.BigAutoField"
