from wagtail_mcp.settings import get_agent_config, get_config


def test_defaults():
    assert get_config() == {
        "require_auth": True,
        "agent_model": "",
        "agent_api_key": "",
        "agent_base_url": "",
    }


def test_override(settings):
    settings.WAGTAIL_MCP = {"require_auth": False}
    assert get_config()["require_auth"] is False


def test_partial_override_keeps_defaults(settings):
    # A partial dict must not clobber unspecified defaults.
    settings.WAGTAIL_MCP = {"some_future_option": True}
    assert get_config()["require_auth"] is True


def test_agent_config_env_fallback(settings, monkeypatch):
    # Unset everywhere: the agent runs on TestModel (empty model string).
    monkeypatch.delenv("TENSORX_API_KEY", raising=False)
    monkeypatch.delenv("TENSORX_BASE_URL", raising=False)
    settings.WAGTAIL_MCP = {}
    config = get_agent_config()
    assert config == {"model": "", "api_key": "", "base_url": ""}


def test_agent_config_tensorx_env(settings, monkeypatch):
    monkeypatch.setenv("TENSORX_API_KEY", "tensorx-key")
    monkeypatch.setenv("TENSORX_BASE_URL", "https://tensorx.example")
    settings.WAGTAIL_MCP = {}
    assert get_agent_config() == {
        "model": "",
        "api_key": "tensorx-key",
        "base_url": "https://tensorx.example",
    }


def test_agent_config_settings_override_env(settings, monkeypatch):
    monkeypatch.setenv("TENSORX_API_KEY", "tensorx-key")
    monkeypatch.setenv("TENSORX_BASE_URL", "https://api.tensorx.ai/v1")
    settings.WAGTAIL_MCP = {
        "agent_model": "openai:some-model",
        "agent_api_key": "settings-key",
    }
    # Per-key precedence: a settings value wins; an unset one falls back to
    # the env var (base_url was not overridden).
    assert get_agent_config() == {
        "model": "openai:some-model",
        "api_key": "settings-key",
        "base_url": "https://api.tensorx.ai/v1",
    }
