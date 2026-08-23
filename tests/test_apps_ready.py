import pytest

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings


@pytest.fixture
def ready_config():
    config = AppConfig.create("wagtail_mcp")
    # ready() is normally called by the app registry; invoke it directly to
    # exercise just the readiness check in isolation.
    config.ready()
    return config


@override_settings(INSTALLED_APPS=["wagtail_mcp", "wagtail.api.v3"])
def test_ready_accepts_v3_installed(ready_config):
    pass  # ready() did not raise


@override_settings(INSTALLED_APPS=["wagtail_mcp"])
def test_ready_raises_without_v3():
    config = AppConfig.create("wagtail_mcp")
    with pytest.raises(ImproperlyConfigured):
        config.ready()
