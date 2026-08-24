"""Tests for the media-upload path shared by ``images_create``/``documents_create``.

These exercise ``tools.common.perform_upload`` directly: the root-collection
fallback when the v3 API requires a ``collection`` form field on projects with
more than one Collection, and passthrough of an explicit ``collection_id``.
"""

import types

import pytest

from wagtail_mcp.errors import APIError
from wagtail_mcp.tools.common import perform_upload


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def collection_baseline():
    """Ensure the root Collection exists.

    ``transaction=True`` truncates the DB between tests, wiping the
    migration-seeded root collection that ``_root_collection_id()`` assumes,
    so each test reseeds it here (mirroring the wagtailcore 0025 migration).
    """
    from wagtail.models import Collection

    if not Collection.objects.filter(depth=1).exists():
        Collection.objects.create(name="Root", path="0001", depth=1, numchild=0)


def _dispatch_mock(record):
    """Build a stand-in dispatch module recording calls and returning/resolving.

    ``record`` is a list of outcomes; each item is either a dict to return or an
    exception to raise, consumed in order (the last item repeats). Mutable
    payloads (``form``) are snapshotted so each recorded call reflects exactly
    what was dispatched on that attempt.
    """
    calls = []

    def call_operation(operation_id, **kwargs):
        snapshot = {k: dict(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
        calls.append((operation_id, snapshot))
        outcome = record[len(calls) - 1] if len(calls) - 1 < len(record) else record[-1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    dispatch = types.SimpleNamespace(call_operation=call_operation)
    return dispatch, calls


def test_upload_retries_with_root_collection_when_required():
    """A 422 'collection required' error on a bare upload triggers a retry."""
    from wagtail.models import Collection

    err = APIError(422, {"errors": [{"loc": ["collection"], "type": "required"}]})
    dispatch, calls = _dispatch_mock([err, {"id": 1, "title": "Pixel"}])

    result = perform_upload(
        dispatch,
        "images_create",
        title="Pixel",
        filename="pixel.gif",
        payload=b"GIF89a",
        mime="image/gif",
    )

    assert result == {"id": 1, "title": "Pixel"}
    assert len(calls) == 2
    # First attempt: no collection field.
    assert "collection_id" not in calls[0][1]["form"]
    # Retry injects the root collection id into the dispatched form.
    assert calls[1][1]["form"]["collection_id"] == Collection.get_first_root_node().id


def test_upload_passes_explicit_collection_id_through():
    """An explicit ``collection_id`` is sent on the first (only) attempt."""
    dispatch, calls = _dispatch_mock([{"id": 7, "title": "Doc"}])

    result = perform_upload(
        dispatch,
        "documents_create",
        title="Doc",
        filename="notes.txt",
        payload=b"hi",
        mime="text/plain",
        collection_id=42,
    )

    assert result == {"id": 7, "title": "Doc"}
    assert len(calls) == 1
    assert calls[0][1]["form"]["collection_id"] == 42


def test_upload_does_not_fallback_for_other_422():
    """A non-collection 422 (e.g. title required) is not auto-retried."""
    err = APIError(422, {"errors": [{"loc": ["title"], "type": "required"}]})
    dispatch, calls = _dispatch_mock([err])

    with pytest.raises(APIError) as exc:
        perform_upload(
            dispatch,
            "images_create",
            title="",
            filename="pixel.gif",
            payload=b"GIF89a",
            mime="image/gif",
        )

    assert exc.value.status == 422
    assert len(calls) == 1


def test_upload_does_not_fallback_when_explicit_collection_fails():
    """An explicit ``collection_id`` that fails is NOT auto-*changed* to root."""
    err = APIError(422, {"errors": [{"loc": ["collection"], "type": "required"}]})
    dispatch, calls = _dispatch_mock([err])

    with pytest.raises(APIError) as exc:
        perform_upload(
            dispatch,
            "images_create",
            title="Pixel",
            filename="pixel.gif",
            payload=b"GIF89a",
            mime="image/gif",
            collection_id=42,
        )

    assert exc.value.status == 422
    assert len(calls) == 1
    assert calls[0][1]["form"]["collection_id"] == 42
