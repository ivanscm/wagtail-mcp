"""Create or refresh a Wagtail v3 API token for the demo admin user.

Wagtail only reveals an ``APIToken``'s plaintext once, at creation. This command
makes that deterministic for local development: after ``just demo``/``migrate``
the token used to talk to the MCP server over the v3 API lives at
``demo/.demo_token`` (gitignored).

Strategy: reuse the ``admin`` user that ``load_initial_data`` sets up, and keep a
single token named ``mcp-demo``. If it already exists *and* the ``.demo_token``
file is present, leave everything untouched (the recorded token is still valid).
If only one side exists (token without file, or file without token), delete and
regenerate so the file and the database agree again. The plaintext is printed
once and written to ``demo/.demo_token``.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import APIToken


TOKEN_NAME = "mcp-demo"  # noqa: S105 - a filter label, not a credential


class Command(BaseCommand):
    help = (
        "Create (or refresh) the 'mcp-demo' Wagtail API token for the demo "
        "'admin' user and record its plaintext in demo/.demo_token."
    )

    def handle(self, *args, **options):
        token_file = Path(settings.BASE_DIR) / ".demo_token"

        User = get_user_model()
        user = User.objects.filter(username="admin").first()
        if user is None:
            raise CommandError(
                "No 'admin' user found. Run 'migrate' and 'load_initial_data' "
                "before this command (or run 'just demo')."
            )

        existing = APIToken.objects.filter(name=TOKEN_NAME).first()
        if existing and token_file.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"API token '{TOKEN_NAME}' already exists and "
                    "demo/.demo_token is present; leaving unchanged."
                )
            )
            return

        if existing:
            existing.delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Removed stale '{TOKEN_NAME}' token (demo/.demo_token "
                    "was missing); regenerating."
                )
            )

        _, plaintext = APIToken.create_token(user=user, name=TOKEN_NAME)
        token_file.write_text(plaintext.rstrip("\n") + "\n")
        # Restrict the plaintext token file to the owner: the token authorizes
        # write access to the whole CMS, so it must not be world-readable.
        token_file.chmod(0o600)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created API token '{TOKEN_NAME}': {plaintext}\n"
                f"Recorded in {token_file}"
            )
        )
