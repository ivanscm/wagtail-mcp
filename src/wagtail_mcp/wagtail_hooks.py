from django.urls import include, path
from django.views.i18n import JavaScriptCatalog
from wagtail import hooks
from wagtail.admin.site_summary import SummaryItem


class WagtailMcpSummaryItem(SummaryItem):
    order = 50
    template_name = "wagtail_mcp/admin/wagtail_mcp_summary.html"


@hooks.register("construct_homepage_summary_items")
def register_wagtail_mcp_summary_item(request, summary_items):
    summary_items.append(WagtailMcpSummaryItem(request))


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path(
            "jsi18n/",
            JavaScriptCatalog.as_view(packages=["wagtail_mcp"]),
            name="javascript_catalog",
        ),
        # Add other package-scoped URLs here so they are access-restricted to the admin.
    ]

    return [
        path(
            "wagtail_mcp/",
            include(
                (urls, "wagtail_mcp"),
                namespace="wagtail_mcp",
            ),
        )
    ]
