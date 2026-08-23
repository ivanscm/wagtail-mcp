from wagtail_mcp.settings import get_config


def test_defaults():
    assert get_config() == {"require_auth": True}


def test_override(settings):
    settings.WAGTAIL_MCP = {"require_auth": False}
    assert get_config()["require_auth"] is False


def test_partial_override_keeps_defaults(settings):
    # A partial dict must not clobber unspecified defaults.
    settings.WAGTAIL_MCP = {"some_future_option": True}
    assert get_config()["require_auth"] is True
