"""Mint the APIToken the admin agent uses to call the v3 API.

See docs/contributing/architecture.md.
"""

import logging
import threading

from wagtail.models import APIToken


logger = logging.getLogger(__name__)

# Visible, revocable name — not a secret.
TOKEN_NAME = "wagtail-mcp-admin-agent"  # noqa: S105
# Serialize concurrent first-time token creation per user.
_mint_lock = threading.Lock()
# Process-local user id → APIToken id and unrecoverable plaintext.
_token_cache: dict[int, tuple[int, str]] = {}


def get_api_token(user) -> str:
    """Return a live APIToken plaintext for ``user``, minting one if needed."""
    with _mint_lock:
        cached = _token_cache.get(user.pk)
        if cached is not None:
            token_pk, plaintext = cached
            if user.api_tokens.filter(pk=token_pk, revoked_at__isnull=True).exists():
                return plaintext
            _token_cache.pop(user.pk, None)

        # A previous process may have left a row whose plaintext is gone.
        user.api_tokens.filter(name=TOKEN_NAME).delete()
        api_token, plaintext = APIToken.create_token(user=user, name=TOKEN_NAME)
        _token_cache[user.pk] = (api_token.pk, plaintext)
        logger.info(
            "wagtail_mcp.agent: minted API token %r for user %s", TOKEN_NAME, user
        )
        return plaintext


def clear_cache() -> None:
    """Forget cached token plaintexts (tests)."""
    _token_cache.clear()


__all__ = ["TOKEN_NAME", "clear_cache", "get_api_token"]
