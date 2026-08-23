"""RFC 7807 (application/problem+json) error translation for wagtail-mcp.

The v3 API surfaces failures as RFC 7807 problem documents (see Wagtail's
``wagtail/api/v3/errors.py``):

    {
        "type": "about:blank",
        "title": "Unprocessable Entity",
        "status": 422,
        "detail": "Validation failed",
        "errors": [{"loc": ["body", "title"], "msg": "field required"}],
    }

This module wraps that envelope in a ``APIError`` exception, and formats it
into a single, agent-actionable string for MCP tool errors. Problem documents
are not guaranteed to carry every key (unhandled exceptions or bare status
codes may omit ``detail`` or ``errors``), so the formatter degrades gracefully.
"""

from __future__ import annotations

from typing import Any


# One-line hints, keyed by HTTP status code and appended to the formatted message
# so the model knows how to recover rather than just that the call failed.
_STATUS_HINTS: dict[int, str] = {
    401: "Check that your Wagtail API token is valid, un-revoked, and belongs to an active user.",
    403: "The authenticated user does not have permission to perform this operation. Grant the relevant permission in Wagtail, or use a token for a user that does.",
    404: "The requested resource was not found — list the parent collection or type to find a valid id, then retry.",
}


class APIError(Exception):
    """A failed v3 API call, carrying its RFC 7807 problem document."""

    def __init__(self, status: int, problem: dict[str, Any]):
        self.status = status
        self.problem = problem
        super().__init__(f"API error {status}: {problem.get('title', 'Error')}")


def _status_line(title: Any, status: int) -> str:
    """Return the ``"<title> (<status>)"`` opening line, tolerating a missing title."""
    title_str = str(title) if title else "Error"
    return f"{title_str} ({status})"


def _detail_line(detail: Any) -> str:
    """Return the detail line, tolerating a missing or non-string detail."""
    detail_str = str(detail) if detail else None
    return f": {detail_str}" if detail_str else ""


def _validation_lines(errors: Any) -> list[str]:
    """Flatten the ``errors`` list into ``- <loc>: <msg>`` lines.

    Tolerates absent, non-list, or scalar entries so a malformed envelope never
    crashes the formatter.
    """
    if not isinstance(errors, list):
        return []
    lines: list[str] = []
    for entry in errors:
        if not isinstance(entry, dict):
            continue
        loc = entry.get("loc")
        msg = entry.get("msg")
        loc_str = ".".join(str(part) for part in loc) if isinstance(loc, list) else None
        if loc_str:
            lines.append(f"- {loc_str}: {msg}" if msg is not None else f"- {loc_str}")
        elif msg is not None:
            lines.append(f"- {msg}")
    return lines


def format_api_error(err: APIError) -> str:
    """Render an ``APIError`` as a single, human- and agent-readable string."""
    problem = err.problem or {}
    parts = [
        _status_line(problem.get("title"), err.status)
        + _detail_line(problem.get("detail"))
    ]
    parts.extend(_validation_lines(problem.get("errors")))
    hint = _STATUS_HINTS.get(err.status)
    if hint:
        parts.append(hint)
    return "\n".join(parts)
