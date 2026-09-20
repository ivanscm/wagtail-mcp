from django.test import RequestFactory

from wagtail_mcp.wagtail_hooks import (
    WagtailMcpSummaryItem,
    register_wagtail_mcp_summary_item,
)


def test_summary_item_renders():
    # Regression: the SummaryItem references
    # wagtail_mcp/admin/wagtail_mcp_summary.html, which must ship with the
    # package — otherwise every GET /admin/ fails with TemplateDoesNotExist.
    request = RequestFactory().get("/admin/")
    html = WagtailMcpSummaryItem(request).render_html()
    assert "MCP server" in html
    assert "/mcp/" in html


def test_summary_item_registered_on_hook():
    request = RequestFactory().get("/admin/")
    summary_items = []
    register_wagtail_mcp_summary_item(request, summary_items)
    assert len(summary_items) == 1
    assert isinstance(summary_items[0], WagtailMcpSummaryItem)
