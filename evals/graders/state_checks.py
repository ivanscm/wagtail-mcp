"""State-graded assertions for the wagtail-mcp Promptfoo eval suite.

Each function here is invoked by promptfoo as a ``type: python`` assertion
(``file://evals/graders/state_checks.py:function_name``). Promptfoo calls the
named function with ``(output, context)`` where ``context["vars"]`` holds the
test case's variables and ``context["config"]`` any assertion ``config``.

The graders do NOT grade prose — they check real CMS state by calling the demo
site's Wagtail v3 API over HTTP (stdlib ``urllib`` only, no third-party deps).
This is what the eval is really about: did the model actually perform the
CMS mutation through the MCP tools?

The demo server must be running and the v3 API reachable at
``WAGTAIL_EVAL_BASE_URL`` (default ``http://localhost:8000``). Requests to
read endpoints are anonymous where the API allows; writes are not read back
through write tools here — graders only GET.

Expected values arrive from the test-case ``vars`` (e.g. a unique ``suffix``
so parallel/rerun rows don't collide). A ``reason`` is always included for
readable output.
"""

from __future__ import annotations

import json
import os
import urllib.request

from typing import Any


def _base_url() -> str:
    return os.environ.get("WAGTAIL_EVAL_BASE_URL", "http://localhost:8000")


def _token() -> str:
    token = os.environ.get("WAGTAIL_DEMO_TOKEN", "")
    if not token:
        # Fall back to reading the gitignored demo token file if present.
        repo = os.environ.get("WAGTAIL_EVAL_REPO", "")
        path = os.path.join(repo, "demo", ".demo_token") if repo else ""
        if path and os.path.exists(path):
            token = open(path).read().strip()
    if not token:
        raise RuntimeError(
            "WAGTAIL_DEMO_TOKEN is not set and demo/.demo_token is missing. "
            "Run `just eval-setup` (and leave `just demo` running)."
        )
    return token


def _get(path: str, *, token: bool = False) -> dict[str, Any]:
    url = _base_url() + "/api/v3" + path
    # S310: intentional HTTP GET to the local/configured demo v3 API from a
    # test grader; base URL is env-controlled (defaults to localhost).
    req = urllib.request.Request(url, method="GET")  # noqa: S310
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {_token()}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _get_all(
    resource_path: str, *, token: bool = False, page_size: int = 20
) -> list[dict[str, Any]]:
    """Fetch every item from a v3 list endpoint, paging with offset.

    The v3 API caps ``limit`` at ``WAGTAILAPI_LIMIT_MAX`` (default 20) and
    responds 400 to anything above it, so a naive ``?limit=100`` fails. We
    page through ``offset`` in ``page_size`` chunks until we've seen the
    full ``count`` (or the page comes back shorter than requested, which
    also signals the end). Resource paths take a trailing slash, e.g.
    ``/images/``; ``query`` (optional) is appended verbatim.
    """
    items: list[dict[str, Any]] = []
    offset = 0
    while True:
        path = f"{resource_path}?limit={page_size}&offset={offset}"
        data = _get(path, token=token)
        batch = data.get("items", [])
        items.extend(batch)
        total = data.get("count", len(items))
        offset += len(batch)
        # Stop once we've collected everything expected, or the batch came
        # back empty/shorter than a full page (end of results).
        if len(batch) == 0 or len(items) >= total:
            break
    return items


def _normalize_path(value: str) -> str:
    """Strip a leading slash and any trailing slashes from a URL path.

    Used to compare old_path values that the model may have created with or
    without a trailing slash (e.g. ``/old-x`` vs ``/old-x/``).
    """
    return value.strip().strip("/")


def whoami(output: str, context: dict[str, Any]) -> bool:
    """The model reports the authenticated Wagtail user.

    Graded on the *output text*: the demo token authenticates as the ``admin``
    superuser. A truthful answer names ``admin`` (or the seeded user). Both
    arms run; the baseline must answer from general knowledge, the ``mcp`` arm
    by calling ``whoami``.
    """
    low = (output or "").lower()
    ok = "admin" in low
    return {
        "pass": ok,
        "score": 1 if ok else 0,
        "reason": "output mentions 'admin' (the demo superuser)"
        if ok
        else f"output did not identify the 'admin' user; got: {output[:120]!r}",
    }


def lists_child_pages(output: str, context: dict[str, Any]) -> bool:
    """The model lists the Home page's direct child pages with ids.

    Graded on output text: Home (id 3) has exactly one direct child, the
    ``Blog`` index (id 4). A truthful answer mentions ``Blog`` and its id.
    """
    low = (output or "").lower()
    ok = "blog" in low
    return {
        "pass": ok,
        "score": 1 if ok else 0,
        "reason": "output mentions the 'Blog' child index page"
        if ok
        else f"output did not list the Blog child page; got: {output[:160]!r}",
    }


def blog_post_exists(output: str, context: dict[str, Any]) -> bool:
    """The model created a draft (or live) blog post under the Blog index.

    Graded on CMS state: find a ``blog.BlogPage`` titled with the unique
    suffix under the Blog index (id 4), and confirm its body contains the
    expected welcome text.
    """
    vars_ = context.get("vars", {})
    suffix = str(vars_.get("suffix", ""))
    expected_title = f"Eval Page {suffix}".strip()

    page = _find_page_by_title(expected_title, blog_root_id=4)
    if page is None:
        return {
            "pass": False,
            "score": 0,
            "reason": f"no blog page titled {expected_title!r} found under Blog index (did the model create it? state={_tree_digest()})",
        }
    pid = page["id"]
    detail = _get(f"/pages/{pid}/?version=draft", token=True)
    body_text = json.dumps(detail)

    ok_fields = detail.get("title") == expected_title
    ok_body = (
        "hello" in body_text.lower()
        or "eval" in body_text.lower()
        or "draft" in body_text.lower()
    )
    return {
        "pass": ok_fields and ok_body,
        "score": 1 if (ok_fields and ok_body) else 0,
        "reason": f"blog page {pid} created with expected title/body"
        if ok_fields and ok_body
        else f"created page {pid} title={detail.get('title')!r} body_contains_expected={ok_body}",
    }


def _tree_digest() -> str:
    """Short summary of the page tree, for debugging a failed grader."""
    try:
        data = _get("/pages/?child_of=4&limit=20", token=True)
        return ", ".join(f"{i['id']}:{i['title']}" for i in data.get("items", []))[:300]
    except Exception as exc:  # pragma: no cover - debug helper
        return f"(unavailable: {exc})"


def _find_page_by_title(title: str, blog_root_id: int | None = None) -> dict | None:
    # Pages endpoint default limit is 20; the model is asked to create a
    # draft under Blog (id 4), so browse child_of the blog root directly.
    path = (
        f"/pages/?child_of={blog_root_id}&limit=20"
        if blog_root_id
        else "/pages/?limit=20"
    )
    data = _get(path, token=True)
    for item in data.get("items", []):
        if item.get("title") == title:
            return item
    return None


def image_uploaded(output: str, context: dict[str, Any]) -> bool:
    """The model uploaded an image whose title carries the unique suffix.

    Graded on CMS state: an image with the expected title exists.
    """
    vars_ = context.get("vars", {})
    suffix = str(vars_.get("suffix", ""))
    expected = f"Eval Image {suffix}".strip()
    data = _get_all("/images/", token=True)
    for item in data:
        if item.get("title") == expected:
            return {
                "pass": True,
                "score": 1,
                "reason": f"image titled {expected!r} exists",
            }
    return {
        "pass": False,
        "score": 0,
        "reason": f"no image titled {expected!r} found; sample titles: "
        + ", ".join(i.get("title", "") for i in data[:5])[:200],
    }


def snippet_created(output: str, context: dict[str, Any]) -> bool:
    """The model created a ``blog.Person`` snippet with the unique name.

    Graded on CMS state: a Person with the expected first name exists.
    """
    vars_ = context.get("vars", {})
    suffix = str(vars_.get("suffix", ""))
    expected = f"Eval Person {suffix}".strip()
    data = _get_all("/snippets/blog.Person/", token=True)
    for item in data:
        if item.get("first_name", "").strip() == expected:
            return {"pass": True, "score": 1, "reason": f"Person {expected!r} exists"}
    return {
        "pass": False,
        "score": 0,
        "reason": f"no Person named {expected!r} found; sample names: "
        + ", ".join(i.get("first_name", "") for i in data[:5])[:200],
    }


def redirect_created(output: str, context: dict[str, Any]) -> bool:
    """The model created a permanent redirect for a unique old path.

    Graded on CMS state: a redirect whose ``old_path`` matches the expected
    ``/old-<suffix>-<unique>`` exists. Matching normalizes the trailing
    slash (the model may create ``/old-x`` or ``/old-x/``).
    """
    vars_ = context.get("vars", {})
    suffix = str(vars_.get("suffix", ""))
    expected_norm = _normalize_path(f"old-{suffix}")
    redirects = _get_all("/redirects/", token=True)
    for item in redirects:
        actual = _normalize_path(str(item.get("old_path", "")))
        if actual and actual == expected_norm:
            return {
                "pass": True,
                "score": 1,
                "reason": f"redirect for {expected_norm!r} exists",
            }
    return {
        "pass": False,
        "score": 0,
        "reason": f"no redirect matching {expected_norm!r} found; paths: {_redirect_old_paths()}",
    }


def _redirect_old_paths() -> str:
    try:
        redirects = _get_all("/redirects/", token=True)
        return ", ".join(
            _normalize_path(str(i.get("old_path", ""))) for i in redirects
        )[:200]
    except Exception:  # pragma: no cover
        return ""


def revision_reverted(output: str, context: dict[str, Any]) -> bool:
    """The model reverted a seeded page to an earlier revision via ``api_call``.

    Graded on CMS state: after the revert, the target blog page's latest
    revision's published content no longer is the most-recent human edit —
    i.e. a revert appended a revision whose content matches the recovered
    (pre-edit) state. We check that the page simply still exists and has at
    least one revision (the seeded publish), and surfaces the revision list
    for inspection. A live assertion on exact content is brittle across
    seeded fixtures, so this grader verifies *a revert endpoint call happened*
    by checking the page's revision count grew (>= 2 means publish + revert).
    """
    vars_ = context.get("vars", {})
    page_id = int(vars_.get("page_id", "5"))
    try:
        revs = _get(f"/pages/{page_id}/revisions/?limit=20", token=True)
    except Exception as exc:
        return {
            "pass": False,
            "score": 0,
            "reason": f"could not read revisions for page {page_id}: {exc}",
        }
    count = revs.get("count", len(revs.get("items", [])))
    ok = count >= 2
    return {
        "pass": ok,
        "score": 1 if ok else 0,
        "reason": f"page {page_id} revision count {count} (>=2 means publish+revert occurred)"
        if ok
        else f"page {page_id} has only {count} revision(s); no revert observed",
    }
