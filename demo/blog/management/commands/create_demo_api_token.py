"""Create or refresh Wagtail v3 API tokens for the demo admin and editor users.

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

The same applies to the ``editor`` user's ``mcp-demo-editor`` token, recorded in
``demo/.demo_token_editor``.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import APIToken


# (username, token name, token file) for each demo token. The editor token
# belongs to a non-superuser in the Editors group, to test permission checks.
TOKENS = [
    ("admin", "mcp-demo", ".demo_token"),
    ("editor", "mcp-demo-editor", ".demo_token_editor"),
]


class Command(BaseCommand):
    help = (
        "Create (or refresh) the 'mcp-demo' Wagtail API token for the demo "
        "'admin' user and record its plaintext in demo/.demo_token, plus an "
        "'mcp-demo-editor' token for the 'editor' user in demo/.demo_token_editor."
    )

    def handle(self, *args, **options):
        for username, token_name, filename in TOKENS:
            self.create_token(username, token_name, Path(settings.BASE_DIR) / filename)

    def create_token(self, username, token_name, token_file):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(
                f"No '{username}' user found. Run 'migrate' and 'load_initial_data' "
                "before this command (or run 'just demo')."
            )

        existing = APIToken.objects.filter(name=token_name).first()
        if existing and token_file.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"API token '{token_name}' already exists and "
                    f"demo/{token_file.name} is present; leaving unchanged."
                )
            )
            return

        if existing:
            existing.delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Removed stale '{token_name}' token (demo/{token_file.name} "
                    "was missing); regenerating."
                )
            )

        _, plaintext = APIToken.create_token(user=user, name=token_name)
        token_file.write_text(plaintext.rstrip("\n") + "\n")
        # Restrict the plaintext token file to the owner: the token authorizes
        # write access to the CMS, so it must not be world-readable.
        token_file.chmod(0o600)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created API token '{token_name}': {plaintext}\n"
                f"Recorded in {token_file}"
            )
        )
