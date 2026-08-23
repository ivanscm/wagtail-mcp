import pytest

from conftest import make_token
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.test import RequestFactory
from wagtail.models import APIToken

from wagtail_mcp.auth import resolve_bearer


pytestmark = pytest.mark.django_db


def test_resolve_bearer_returns_token():
    token = make_token()
    request = RequestFactory().get("/mcp/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resolve_bearer(request) == token


def test_resolve_bearer_missing_header_is_none():
    request = RequestFactory().get("/mcp/")
    assert resolve_bearer(request) is None


def test_resolve_bearer_wrong_scheme_is_none():
    token = make_token()
    request = RequestFactory().get("/mcp/", HTTP_AUTHORIZATION=f"Basic {token}")
    assert resolve_bearer(request) is None


def test_resolve_bearer_rejects_garbage():
    request = RequestFactory().get("/mcp/", HTTP_AUTHORIZATION="Bearer nope")
    assert resolve_bearer(request) is None


def test_resolve_bearer_rejects_revoked():
    token = make_token()
    APIToken.objects.get().revoke()
    request = RequestFactory().get("/mcp/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resolve_bearer(request) is None


def test_resolve_bearer_rejects_inactive_user():
    user = get_user_model().objects.create_superuser("inactive", "i@example.com", "pw")
    user.is_active = False
    user.save()
    token = make_token(user)
    request = RequestFactory().get("/mcp/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resolve_bearer(request) is None


def test_resolve_bearer_returns_none_for_empty_request():
    assert resolve_bearer(HttpRequest()) is None
