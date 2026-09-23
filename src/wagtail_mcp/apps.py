from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class WagtailMCPAppConfig(AppConfig):
    label = "wagtail_mcp"
    name = "wagtail_mcp"
    verbose_name = "Wagtail MCP"

    def ready(self):
        # Dispatch depends on the Wagtail v3 API.
        if "wagtail.api.v3" not in settings.INSTALLED_APPS:
            raise ImproperlyConfigured(
                "wagtail-mcp requires the Wagtail v3 API. Add 'wagtail.api.v3' to "
                "your project's INSTALLED_APPS, then mount it in your URLConf "
                "(e.g. path('api/v3/', wagtail.api.v3.urls.api.urls))."
            )
