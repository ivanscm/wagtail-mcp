from .base import *  # noqa: F403


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-s29(yxq@%u+&l5!4gqn(u$&bp_^ncsp&@sl2dr+-h_+^s(g7@2"  # noqa: S105

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Absolute API base URL for the v3 API's self-referential links
# (meta.detail_url). wagtail-mcp dispatches through Django's in-process test
# client; setting this (matching the local runserver scheme/host) keeps those
# URLs correct without depending on host forwarding from the client request.
WAGTAILAPI_BASE_URL = "http://localhost:8000"


try:
    from .local import *  # noqa: F403
except ImportError:
    pass
