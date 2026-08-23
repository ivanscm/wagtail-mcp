import base64
import json as json_module

from unittest import mock

import pytest

from wagtail.images import get_image_model
from wagtail.models import Page, Site

from wagtail_mcp import dispatch
from wagtail_mcp.dispatch import call_operation, clear_caches, openapi, operation_map
from wagtail_mcp.errors import APIError
from wagtail_mcp.test.models import ContentPage


pytestmark = pytest.mark.django_db


@pytest.fixture
def root_page():
    # Wagtail's default home page (depth 2) from migrations.
    return Page.objects.filter(depth=2).first() or Page.objects.get(depth=1)


def test_operation_map_known_ids():
    ops = operation_map()
    # Exact (method, path) after mount-prefix stripping:
    # OpenAPI path is /api/v3/whoami/, stripped to whoami/.
    assert ops["whoami"] == ("get", "whoami/")
    assert ops["pages_create"] == ("post", "pages/")
    assert ops["pages_detail"] == ("get", "pages/{page_id}/")
    assert ops["images_create"][0] == "post"
    # The locales router is mounted only when ``wagtail.locales`` is installed;
    # this pins that the test settings include it (regression for task 6 review).
    assert "locales_list" in ops
    assert "locales_detail" in ops


def test_call_operation_get_with_query(root_page, token):
    hostname = "example.test"
    Site.objects.create(hostname=hostname, root_page=root_page, is_default_site=False)
    data = call_operation("sites_list", query={"limit": 10}, token=token)
    assert data["count"] >= 1
    hostnames = [item["hostname"] for item in data["items"]]
    assert hostname in hostnames


def test_call_operation_unauthorized_raises():
    bad_token = "wagtail_invalidtoken"  # noqa: S105  -- deliberately invalid bearer, not a real credential
    with pytest.raises(APIError) as exc:
        call_operation("pages_create", body={}, token=bad_token)
    assert exc.value.status in (401, 403)


def test_call_operation_404(token, root_page):
    with pytest.raises(APIError) as exc:
        call_operation(
            "pages_detail",
            path_params={"page_id": 999999},
            token=token,
        )
    assert exc.value.status == 404


def test_call_operation_validation_problem(token, root_page):
    with pytest.raises(APIError) as exc:
        call_operation(
            "pages_create",
            body={"meta": {"type": "wagtail_mcp_test.ContentPage"}},
            token=token,
        )
    assert exc.value.status == 422
    assert exc.value.problem["errors"]


def test_upload_image_multipart(root_page, token):
    gif = base64.b64decode(
        "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
    )
    data = call_operation(
        "images_create",
        form={"title": "dispatch-test"},
        files={"file": ("pixel.gif", gif, "image/gif")},
        token=token,
    )
    assert data["title"] == "dispatch-test"
    assert get_image_model().objects.filter(title="dispatch-test").exists()


def test_openapi_cached_and_clearable():
    first = openapi()
    assert first is openapi()
    openapi.cache_clear()
    assert openapi() is not first


def test_pages_delete_returns_none(root_page, token):
    # pages_delete responds 204 with an empty body → call_operation returns None.
    child = ContentPage(title="To delete", slug="to-delete")
    root_page.add_child(instance=child)
    result = call_operation(
        "pages_delete", path_params={"page_id": child.pk}, token=token
    )
    assert result is None


def test_missing_path_param_raises_clean_apierror(token):
    # pages_detail requires {page_id} in its path template.
    with pytest.raises(APIError) as exc:
        call_operation("pages_detail", token=token)
    assert exc.value.status == 400
    assert "page_id" in exc.value.problem["detail"]


def test_body_with_form_raises_clean_apierror(token):
    with pytest.raises(APIError) as exc:
        call_operation(
            "pages_create",
            body={"meta": {"type": "x"}},
            form={"title": "y"},
            token=token,
        )
    assert exc.value.status == 400
    assert "not both" in exc.value.problem["detail"]


class FakeResponse:
    """Minimal stand-in for ninja.testing.NinjaResponse."""

    def __init__(self, *, status_code, content=None):
        self.status_code = status_code
        self.content = content if content is not None else b""

    def json(self):
        return json_module.loads(self.content if self.content else "{}")


class FakeClient:
    """Records the request it is asked to make and returns a fixed response."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(
        self,
        method,
        path,
        data=None,
        json=None,
        query_params=None,
        headers=None,
        FILES=None,
    ):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "query_params": query_params,
                "headers": headers or {},
            }
        )
        return self.response


def test_non_envelope_5xx_normalized():
    # A 5xx that is not problem+json must surface as a normalized "Unexpected
    # response" APIError rather than crash parsing the body. These tests warm
    # the operation_map cache via the real client first, then swap in the fake.
    operation_map()  # warm cache so call_operation does not hit openapi()
    fake = FakeClient(FakeResponse(status_code=500, content=b"Internal Server Error"))
    with mock.patch.object(dispatch, "_client", return_value=fake):
        with pytest.raises(APIError) as exc:
            call_operation("whoami")
    assert exc.value.status == 500
    assert exc.value.problem["title"] == "Unexpected response"


def test_query_none_values_dropped():
    operation_map()  # warm cache
    fake = FakeClient(FakeResponse(status_code=200, content=b"{}"))
    with mock.patch.object(dispatch, "_client", return_value=fake):
        call_operation("sites_list", query={"limit": 20, "offset": None})
    sent = fake.calls[0]["query_params"]
    assert sent == {"limit": 20}
    assert "offset" not in sent


def test_empty_response_returns_none():
    operation_map()  # warm cache
    fake = FakeClient(FakeResponse(status_code=204, content=b""))
    with mock.patch.object(dispatch, "_client", return_value=fake):
        # pages_actions_unpublish returns an empty body; supply its path param
        # so the request actually fires and the 204 branch is exercised.
        result = call_operation("pages_actions_unpublish", path_params={"page_id": 1})
    assert result is None


def test_no_token_omits_authorization_header():
    # With neither token nor current_token set, we must not send "Bearer None".
    operation_map()  # warm cache
    fake = FakeClient(FakeResponse(status_code=200, content=b"{}"))
    with mock.patch.object(dispatch, "_client", return_value=fake):
        call_operation("sites_list", query={"limit": 5})
    sent_headers = fake.calls[0]["headers"]
    assert "Authorization" not in sent_headers


def test_clear_caches_invalidates_all():
    # Must run after the fake-client tests so the operation_map cache is warm
    # and a fresh openapi() fetch is observable. Keeping it last avoids
    # disturbing earlier tests' shared cache.
    first_schema = openapi()
    assert openapi() is first_schema
    first_ops = operation_map()
    assert operation_map() is first_ops
    clear_caches()
    assert openapi() is not first_schema
    assert operation_map() is not first_ops
    assert operation_map()["whoami"] == ("get", "whoami/")
    # Leave a warm cache behind for any trailing collection needs.
    operation_map()
