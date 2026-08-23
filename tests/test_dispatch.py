import base64

import pytest

from wagtail.images import get_image_model
from wagtail.models import Page, Site

from wagtail_mcp.dispatch import call_operation, openapi, operation_map
from wagtail_mcp.errors import APIError


pytestmark = pytest.mark.django_db


@pytest.fixture
def root_page():
    # Wagtail's default home page (depth 2) from migrations.
    return Page.objects.filter(depth=2).first() or Page.objects.get(depth=1)


def test_operation_map_known_ids():
    ops = operation_map()
    assert ops["whoami"][0] == "get"
    assert ops["pages_create"][0] == "post"
    assert ops["pages_detail"][0] == "get"
    assert "images_create" in ops


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


def test_openapi_cached_and_clearable():
    first = openapi()
    assert first is openapi()
    openapi.cache_clear()
    assert openapi() is not first


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
