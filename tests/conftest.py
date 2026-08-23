import pytest

from django.contrib.auth import get_user_model
from wagtail.models import APIToken


@pytest.fixture(autouse=True)
def temporary_media_dir(settings, tmp_path: pytest.TempdirFactory):
    settings.MEDIA_ROOT = tmp_path / "media"


def make_token(user=None):
    """Create a superuser + Wagtail API token, returning the plaintext token.

    Used by every layer of the test suite (dispatching through v3 requires an
    authenticated user held in an APIToken). The plaintext is only returned
    here — the APIToken model never stores it.
    """
    user = user or get_user_model().objects.create_superuser(
        "admin", "a@example.com", "pw"
    )
    _, plaintext = APIToken.create_token(user=user, name="test")
    return plaintext


@pytest.fixture
def token():
    return make_token()
