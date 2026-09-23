"""
ASGI config for demo project.

Exposes the ASGI callable as a module-level variable named ``application``.

``just runserver-asgi`` serves the site through this module so the admin
agent's SSE response flushes incrementally (WSGI buffers it).

https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings.dev")

application = get_asgi_application()
